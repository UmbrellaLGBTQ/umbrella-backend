from fastapi import APIRouter
from ..schemas import CountryPhoneData

router = APIRouter(
    prefix="/meta",
    tags=["metadata"]
)

@router.get("/country-codes")
def get_country_codes():
    """Return a list of supported country codes with display names and formatting examples"""
    return CountryPhoneData().get_all_country_codes()
