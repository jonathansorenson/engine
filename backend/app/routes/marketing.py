"""Marketing page routes — public, server-rendered HTML for SEO."""

from pathlib import Path
from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates

router = APIRouter(tags=["marketing"])

# Resolve templates directory (Docker vs local dev)
_docker_frontend = Path("/frontend")
_local_frontend = Path(__file__).resolve().parent.parent.parent.parent / "frontend"
_frontend_dir = _docker_frontend if _docker_frontend.exists() else _local_frontend
templates = Jinja2Templates(directory=str(_frontend_dir / "templates"))


@router.get("/engine/features", include_in_schema=False)
async def features_page(request: Request):
    return templates.TemplateResponse("features.html", {"request": request})


@router.get("/engine/pricing", include_in_schema=False)
async def pricing_page(request: Request):
    return templates.TemplateResponse("pricing.html", {"request": request})


@router.get("/engine/demo", include_in_schema=False)
async def demo_page(request: Request):
    return templates.TemplateResponse("demo.html", {"request": request})


@router.get("/engine/how-it-works", include_in_schema=False)
async def how_it_works_page(request: Request):
    return templates.TemplateResponse("how-it-works.html", {"request": request})


@router.get("/engine/integrations", include_in_schema=False)
async def integrations_page(request: Request):
    return templates.TemplateResponse("integrations.html", {"request": request})


@router.get("/engine/enterprise", include_in_schema=False)
async def enterprise_page(request: Request):
    return templates.TemplateResponse("enterprise.html", {"request": request})


@router.get("/engine/changelog", include_in_schema=False)
async def changelog_page(request: Request):
    return templates.TemplateResponse("changelog.html", {"request": request})
