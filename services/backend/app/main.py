"""
POC Backend Service
Provides health check endpoint with actual PostgreSQL connectivity verification
"""
import os
import time
from datetime import datetime, timezone
from typing import Dict, Any

from fastapi import FastAPI, Response, status
from fastapi.middleware.cors import CORSMiddleware
import psycopg2
from psycopg2 import OperationalError, sql


app = FastAPI(
    title="POC Backend",
    version="1.0.0",
    description="Backend service for Evidence-Gated Cloud Change Impact POC"
)

# CORS middleware to allow Frontend to call Backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database configuration from environment variables
DATABASE_CONFIG = {
    "host": os.getenv("DATABASE_HOST", "database-service"),
    "port": int(os.getenv("DATABASE_PORT", "5432")),
    "database": os.getenv("DATABASE_NAME", "appdb"),
    "user": os.getenv("DATABASE_USER", "appuser"),
    "password": os.getenv("DATABASE_PASSWORD", "apppassword"),
}


def check_database_connectivity() -> Dict[str, Any]:
    """
    Verify actual PostgreSQL database connectivity by executing a test query.
    
    Returns:
        Dictionary with database connectivity status, version, query result, and timing
    """
    start_time = time.time()
    
    try:
        # Establish connection
        conn = psycopg2.connect(
            host=DATABASE_CONFIG["host"],
            port=DATABASE_CONFIG["port"],
            database=DATABASE_CONFIG["database"],
            user=DATABASE_CONFIG["user"],
            password=DATABASE_CONFIG["password"],
            connect_timeout=5
        )
        
        # Create cursor and execute test query
        cursor = conn.cursor()
        cursor.execute("SELECT 1 AS result")
        result = cursor.fetchone()
        
        # Get database version
        cursor.execute("SELECT version()")
        version = cursor.fetchone()[0]
        
        # Calculate response time
        response_time_ms = round((time.time() - start_time) * 1000, 2)
        
        # Close resources
        cursor.close()
        conn.close()
        
        return {
            "connected": True,
            "version": version,
            "test_query": "SELECT 1 AS result",
            "query_result": result[0] if result else None,
            "response_time_ms": response_time_ms
        }
        
    except OperationalError as e:
        # Database connection failed
        response_time_ms = round((time.time() - start_time) * 1000, 2)
        return {
            "connected": False,
            "error": str(e).split('\n')[0],  # First line of error
            "last_attempt": datetime.now(timezone.utc).isoformat(),
            "response_time_ms": response_time_ms
        }
    except Exception as e:
        # Other unexpected errors
        response_time_ms = round((time.time() - start_time) * 1000, 2)
        return {
            "connected": False,
            "error": f"Unexpected error: {str(e)}",
            "last_attempt": datetime.now(timezone.utc).isoformat(),
            "response_time_ms": response_time_ms
        }


@app.get("/health")
async def health_check(response: Response):
    """
    Health check endpoint that verifies both application and database health.
    
    Returns HTTP 200 only when BOTH application AND database are healthy.
    Returns HTTP 503 when database is unreachable.
    
    This endpoint is used by:
    - Kubernetes readiness/liveness probes
    - Frontend to display system status
    - Baseline verification script
    """
    # Check application health (if we're here, FastAPI is running)
    application_status = {
        "name": "poc-backend",
        "version": "1.0.0",
        "status": "running"
    }
    
    # Check database connectivity (actual query execution)
    database_status = check_database_connectivity()
    
    # Determine overall health status
    if database_status["connected"]:
        overall_status = "healthy"
        response.status_code = status.HTTP_200_OK
    else:
        overall_status = "unhealthy"
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    
    return {
        "status": overall_status,
        "application": application_status,
        "database": database_status,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@app.get("/live")
async def liveness_check():
    """
    Liveness check endpoint - verifies application process is alive.

    Returns HTTP 200 if FastAPI application is responsive.
    Does NOT check database or external dependencies.

    Used by Kubernetes liveness probe to determine if container should be restarted.
    """
    return {
        "status": "alive",
        "application": {
            "name": "poc-backend",
            "version": "1.0.0"
        },
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@app.get("/")
async def root():
    """Root endpoint - simple service identification"""
    return {
        "service": "poc-backend",
        "version": "1.0.0",
        "endpoints": {
            "health": "/health",
            "docs": "/docs"
        }
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )
