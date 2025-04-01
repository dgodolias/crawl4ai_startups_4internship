from pydantic import BaseModel


class Venue(BaseModel):
    """
    Represents the data structure of a Venue.
    """

    name: str
    location: str
    price: str
    capacity: str
    rating: float
    reviews: int
    description: str


class Startup(BaseModel):
    """
    Represents the data structure of a Startup from F6S.
    """
    
    name: str
    website: str
    email: str = ""
    description: str = ""
    location: str = ""
    industry: str = ""
