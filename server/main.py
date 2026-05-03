import asyncio
import logging
import sys
import uuid

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

from server import settings
from server.models import (
    DedrmErrorResponse,
    DedrmRequest,
    DedrmSuccessResponse,
    HealthResponse,
)
from server.runner import (
    PathValidationError,
    get_libgourou_version,
    run_dedrm,
)

logging.basicConfig(
    level=settings.LOG_LEVEL,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("svc-libgourou")

app = FastAPI(title="svc-libgourou", version="1.0.0", docs_url="/docs", redoc_url=None)


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    version = await get_libgourou_version()
    return HealthResponse(ok=True, version=version)


@app.post(
    "/dedrm",
    response_model=DedrmSuccessResponse,
    responses={
        400: {"model": DedrmErrorResponse},
        502: {"model": DedrmErrorResponse},
        504: {"model": DedrmErrorResponse},
    },
)
async def dedrm(req: DedrmRequest):
    request_id = uuid.uuid4().hex[:12]
    logger.info(
        f"dedrm start id={request_id} acsm={req.acsm_file} "
        f"drm={req.drm_file} out={req.output_dir}/{req.output_file}"
    )

    try:
        result = await run_dedrm(req)
    except PathValidationError as exc:
        logger.warning(f"dedrm path_invalid id={request_id} err={exc}")
        raise HTTPException(status_code=400, detail=str(exc))
    except asyncio.TimeoutError:
        logger.error(f"dedrm timeout id={request_id} timeout={settings.REQUEST_TIMEOUT}s")
        return JSONResponse(
            status_code=504,
            content=DedrmErrorResponse(
                stage="subprocess",
                error=f"timeout after {settings.REQUEST_TIMEOUT}s",
            ).model_dump(),
        )
    except FileNotFoundError as exc:
        logger.error(f"dedrm binary_missing id={request_id} err={exc}")
        raise HTTPException(status_code=500, detail=f"binary not found: {exc}")

    if result.get("ok"):
        logger.info(
            f"dedrm ok id={request_id} duration_ms={result['duration_ms']} "
            f"out={result['output_path']}"
        )
        return result

    logger.warning(
        f"dedrm fail id={request_id} stage={result.get('stage')} "
        f"exit={result.get('exit_code')} stderr={result.get('stderr', '')[:300]!r}"
    )
    return JSONResponse(status_code=502, content=result)
