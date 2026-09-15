from datetime import date
from pydantic import BaseModel, ConfigDict, Field, StrictInt, StrictStr, field_validator

class CreateTaskPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    farm_id: StrictInt = Field(alias="farmId", gt=0)
    task_no: StrictStr = Field(alias="taskNo", min_length=3, max_length=40, pattern=r"^[A-Za-z0-9_-]+$")
    title: StrictStr = Field(min_length=2, max_length=120)
    due_date: date = Field(alias="dueDate")
    notes: StrictStr | None = Field(default=None, max_length=2000)
    @field_validator("task_no")
    @classmethod
    def normalize(cls, value): return value.upper()

class TaskListQuery(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    farm_id: int = Field(alias="farmId", gt=0)
    status: str = "all"

