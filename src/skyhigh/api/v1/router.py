from fastapi import APIRouter

from skyhigh.api.v1 import checkin, checkin_flow, flights, health

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(checkin.router, prefix="/seats")
api_router.include_router(flights.router, prefix="/flights")
api_router.include_router(checkin_flow.router, prefix="/checkin")
