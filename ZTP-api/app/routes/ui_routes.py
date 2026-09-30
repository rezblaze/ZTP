# import logging

# from fastapi import APIRouter, HTTPException
# from fastapi.responses import FileResponse

# logger = logging.getLogger(__name__)

# router = APIRouter()


# @router.get("/", tags=["UI"])
# async def read_index():
#     try:
#         return FileResponse(f"app/static/index.html")
#     except FileNotFoundError:
#         raise HTTPException(status_code=404, detail="File not found")
