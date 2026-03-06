from fastapi import FastAPI
from app.db.session import Base, engine
from app.api.jobs import router as jobs_router
from fastapi.middleware.cors import CORSMiddleware

# MAIN ENTRY POINT  - Connects frontend to backend

# Initialize FastAPI 
app = FastAPI(title="Agentic CAD Converter")

# Add CORS middleware (for react frontend running on localhost:5173)
# cors = cross-origin resource sharing, allows frontend to make requests to backend
app.add_middleware(
    CORSMiddleware,
    # starts web server
    allow_origins=["http://localhost:5173"],
    allow_credentials=True, # allows cookies if needed
    allow_methods=["*"], # allows all HTTP methods
    allow_headers=["*"], # allows all headers
)

# Create database tables
Base.metadata.create_all(bind=engine)

# Include API routes
app.include_router(jobs_router)