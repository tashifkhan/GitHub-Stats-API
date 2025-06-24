from fastapi import APIRouter

pr_router = APIRouter()


@pr_router.get("/{username}/prs")
async def get_user_prs(username: str):
    return {"message": "Hello, World!"}
