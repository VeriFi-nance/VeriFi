from typing import List, Optional, Any
from pydantic import BaseModel, Field, AliasChoices, BeforeValidator
from typing_extensions import Annotated

def force_str(v: Any) -> str:
    if v is None: return ""
    if isinstance(v, list): return ", ".join(map(str, v))
    return str(v)

class ClaimDetails(BaseModel):
    subject_object: Annotated[str, BeforeValidator(force_str)] = Field(
        default="", validation_alias=AliasChoices('subject_object', 'entity', 'asset', 'subject')
    )
    quantity: Annotated[str, BeforeValidator(force_str)] = Field(
        default="", validation_alias=AliasChoices('quantity', 'amount', 'value', 'price')
    )
    time_frame: Annotated[str, BeforeValidator(force_str)] = Field(
        default="", validation_alias=AliasChoices('time_frame', 'timeframe', 'period', 'date')
    )
    claim_text: Annotated[str, BeforeValidator(force_str)] = Field(
        default="", validation_alias=AliasChoices('claim_text', 'text', 'claim')
    )

    def is_valid_claim(self) -> bool:
        """Kodun çalışması için bu metodun burada olması şarttır."""
        # Miktarda rakam veya % var mı kontrolü
        has_number = any(char.isdigit() for char in self.quantity) or "%" in self.quantity
        return has_number and bool(self.subject_object) and bool(self.time_frame)

class HardClaimExtractor(BaseModel):
    detected_language: str = "tr"
    status: str = "success"
    claims: List[ClaimDetails] = []
    reason: Optional[str] = None