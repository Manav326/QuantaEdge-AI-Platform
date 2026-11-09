from fastapi import APIRouter, Depends

from app.core.layers import get_layers
from app.security import ClientPrincipal, require_scope
from app.schemas import ModelProfile

router = APIRouter(prefix="/v1/models", tags=["model registry"])


@router.get("", response_model=list[ModelProfile])
async def list_models(_: ClientPrincipal = Depends(require_scope("models:read"))) -> list[ModelProfile]:
    layers = get_layers()
    output = []
    for profile_id, item in layers.layer("models").get("models", {}).items():
        if not item.get("enabled", False):
            continue
        output.append(ModelProfile(
            id=profile_id,
            display_name=item.get("display_name", profile_id),
            provider=item["provider"],
            capabilities=item.get("capabilities", []),
            context_window=item.get("context_window"),
            dimensions=item.get("dimensions"),
            quality_status=item.get("quality_status", "unclassified"),
        ))
    return output
