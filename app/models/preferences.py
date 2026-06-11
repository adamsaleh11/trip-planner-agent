"""Preference schemas for the five fixed categories.

These schemas are the contract between the preference forms (frontend), this
API, and the Phase 3 category agents. Validation is strict on purpose: enums
reject junk now so agent prompts never see garbage later.
"""

from typing import List, Literal, Optional

from pydantic import BaseModel, Field, model_validator

BudgetCurrency = Literal["USD", "CAD"]

# Average spend the member picked on the budget slider. Legacy documents
# stored "$" / "$$" / "$$$"; those coerce to representative USD amounts so
# old preferences keep validating.
LEGACY_BUDGET_AMOUNTS = {"$": 30, "$$": 75, "$$$": 150}


class Budget(BaseModel):
    amount: int = Field(ge=0, le=500)
    currency: BudgetCurrency = "USD"

    @model_validator(mode="before")
    @classmethod
    def _coerce_legacy_tier(cls, value):
        if isinstance(value, str) and value in LEGACY_BUDGET_AMOUNTS:
            return {"amount": LEGACY_BUDGET_AMOUNTS[value], "currency": "USD"}
        return value

FREE_TEXT = Field(default="", max_length=2000)


class FoodDrink(BaseModel):
    schemaVersion: int = 1
    freeText: str = FREE_TEXT
    dietaryRestrictions: List[
        Literal["vegetarian", "vegan", "halal", "kosher", "gluten_free", "none"]
    ] = Field(default_factory=list)
    cuisineInterests: List[str] = Field(default_factory=list)
    mealBudget: Optional[Budget] = None
    drinkInterests: List[Literal["local_drinks", "cocktails", "coffee", "none"]] = Field(
        default_factory=list
    )
    sportsBarInterest: bool = False


class OutdoorsScenic(BaseModel):
    schemaVersion: int = 1
    freeText: str = FREE_TEXT
    activityLevel: Optional[Literal["chill", "moderate", "strenuous"]] = None
    interests: List[
        Literal["hikes", "beaches", "viewpoints", "sunsets", "water_activities", "parks"]
    ] = Field(default_factory=list)
    photoSpotsPriority: bool = False


class Nightlife(BaseModel):
    schemaVersion: int = 1
    freeText: str = FREE_TEXT
    vibe: List[
        Literal["clubs", "bars", "live_music", "street_parties", "chill_drinks", "none"]
    ] = Field(default_factory=list)
    frequency: Optional[Literal["none", "once_or_twice", "most_nights"]] = None
    budget: Optional[Budget] = None


class CultureLocal(BaseModel):
    schemaVersion: int = 1
    freeText: str = FREE_TEXT
    interests: List[
        Literal[
            "markets", "museums", "landmarks", "neighborhoods", "local_events", "side_quests"
        ]
    ] = Field(default_factory=list)
    guidedTours: Optional[Literal["yes", "no", "maybe"]] = None


class Logistics(BaseModel):
    schemaVersion: int = 1
    freeText: str = FREE_TEXT
    pace: Optional[Literal["relaxed", "balanced", "packed"]] = None
    wakeTime: Optional[Literal["early", "mid", "late"]] = None
    transport: List[Literal["walk", "transit", "rideshare", "rental_car"]] = Field(
        default_factory=list
    )
    dailyBudget: Optional[Budget] = None
    mobilityNotes: str = Field(default="", max_length=1000)


CATEGORY_MODELS = {
    "food_drink": FoodDrink,
    "outdoors_scenic": OutdoorsScenic,
    "nightlife": Nightlife,
    "culture_local": CultureLocal,
    "logistics": Logistics,
}

CATEGORIES = list(CATEGORY_MODELS)


class MemberPreferences(BaseModel):
    """One member's preferences across all categories; null = not filled."""

    food_drink: Optional[FoodDrink] = None
    outdoors_scenic: Optional[OutdoorsScenic] = None
    nightlife: Optional[Nightlife] = None
    culture_local: Optional[CultureLocal] = None
    logistics: Optional[Logistics] = None


class GroupPreferencesEntry(BaseModel):
    participantId: str
    displayName: Optional[str] = None
    claimedByUid: Optional[str] = None
    preferences: MemberPreferences


class CompletionEntry(BaseModel):
    participantId: str
    displayName: Optional[str] = None
    claimedByUid: Optional[str] = None
    filled: dict[str, bool]
