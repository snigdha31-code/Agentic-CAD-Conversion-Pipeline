import json
import httpx
from app.core.config import settings
from app.agent.schemas import Plan

# this file defines the planner function that generates a conversion plan based on input file characteristics 
# and history of attempts, using OpenRouter API to get AI-generated plans, 
# with a deterministic fallback plan if the API call fails or returns invalid data.

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

SYSTEM_PROMPT = """You are a conversion planning agent for a CAD conversion service.
Return ONLY valid JSON matching this schema:
{
  "attempts":[
    {"provider":"cloudconvert","output_type":"pdf|png|jpg","params":{...}}
  ],
  "validation":{"min_kb":50,"max_runtime_sec":180},
  "user_facing_failure_message":"..."
}
No prose. No markdown.
Use 2-3 attempts with small param changes for reliability:
- For pdf: try page_size A3 then A1, fit_mode drawing, dpi 300
- For images: dpi 300 then 600
"""

# Fallback plan if OpenRouter API fails or returns invalid data - 
# this ensures we always have a conversion strategy to try, even if it's not optimized for the specific file characteristics.
async def make_plan(input_ext: str, output_type: str, file_size_mb: float, history: list) -> Plan:
    
    # Deterministic fallback plan (so job doesn't fail if OpenRouter errors)
    fallback = Plan.model_validate({
        "attempts": [
            
        # first attempt with standard parameters, which should work for most cases and is faster than high DPI
        {"provider": "cloudconvert", "output_type": output_type,
         "params": {"dpi": 300, "page_size": "A3", "fit_mode": "drawing"}},

        # second attempt with more aggressive parameters in case the first one produces blank/cropped output, \
        # which can happen for CAD->PDF conversions due to PDF viewport issues.
        {"provider": "cloudconvert", "output_type": output_type,
         "params": {"dpi": 300, "page_size": "A0", "fit_mode": "drawing"}},

        # PNG fallback (high DPI) -> then we convert PNG to PDF in worker if requested
        # high DPI means more pixels, which can help avoid blank/cropped output
        # for CAD->PDF conversions that sometimes happens due to PDF viewport issues
        {"provider": "cloudconvert", "output_type": "png",
         "params": {"dpi": 900, "pipeline_png_to_pdf": True}},
        # png to pdf pipeline is a rescue strategy for cases where direct CAD->PDF conversion produces blank/cropped PDFs due to viewport issues.
    ],
    "validation": {"min_kb": 5, "max_runtime_sec": 180},
    "user_facing_failure_message": "Conversion produced blank/cropped output. Try re-saving DXF with correct extents or move geometry closer to origin."
         })

    api_key = getattr(settings, "OPENROUTER_API_KEY", None)
    model = getattr(settings, "OPENROUTER_MODEL", "openai/gpt-4o-mini")

    if not api_key or api_key == "YOUR_OPENROUTER_KEY":
        return fallback

    user_payload = {
        "input_ext": input_ext,
        "output_type": output_type,
        "file_size_mb": file_size_mb,
        "history": history,
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(user_payload)},
        ],
        "temperature": 0.2, # temperature means how deterministic vs creative the AI responses are. 
        #0.2 is low, so it will stick closely to the prompt and produce more consistent plans, which is important for a conversion planner. 
        # Higher values (e.g. 0.8) would produce more varied plans but could be less reliable.
    }

    try:
        
        # we use httpx AsyncClient to make the API call asynchronously,
        # which is more efficient and allows for better performance in the Celery worker.
        async with httpx.AsyncClient(timeout=30) as client:
            
            # make POST request to OpenRouter API with the planning prompt and user payload,
            r = await client.post(OPENROUTER_URL, headers=headers, json=body)
            
            r.raise_for_status() # raise exception for HTTP errors (4xx, 5xx)
            
            content = r.json()["choices"][0]["message"]["content"] 
            # extract the content of the AI response, which should be the JSON plan
            
        # validate and parse the AI response into a Plan object.
        # If the response is not valid JSON or doesn't match the Plan schema, 
        # it will raise an exception and we will return the fallback plan.
        if not content:
            return fallback

        # we expect the AI to return a JSON string that matches the Plan schema,
        data = json.loads(content)
        return Plan.model_validate(data)
    
    # if any exceptions occur (HTTP errors, JSON parsing errors, validation errors),
    # we catch them and return the fallback plan.
    except Exception:
        return fallback