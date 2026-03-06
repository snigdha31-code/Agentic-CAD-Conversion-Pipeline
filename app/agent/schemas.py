from pydantic import BaseModel, Field # for defining data models and validation
from typing import List, Literal, Dict, Any 

# this file defines data models for the conversion plan, which includes a list of conversion attempts 
# and validation criteria.
# data models are defined using Pydantic, which provides validation and 
# parsing of the data according to the specified schema.

Provider = Literal["cloudconvert"]  # can add more providers
OutputType = Literal["pdf", "png", "jpg"]

class Attempt(BaseModel):
    provider: Provider = Literal["cloudconvert", "inkscape"] 
    output_type: OutputType
    params: Dict[str, Any] = Field(default_factory=dict)

# The validation spec defines criteria for validating the output file
# , such as minimum file size and maximum runtime.
class ValidationSpec(BaseModel):
    min_kb: int = 10
    max_runtime_sec: int = 180

# The Plan includes a list of conversion attempts, each with a provider, output type, and parameters.
class Plan(BaseModel):
    attempts: List[Attempt]
    validation: ValidationSpec = ValidationSpec()
    user_facing_failure_message: str = "Conversion failed. Please try exporting to DXF and re-upload."