from pydantic import BaseModel


class Retrieval(BaseModel):
    """
    This tool is used for reading files with the convention "file-(24 character id)" ie. file-yrRwAMZEgS36ACyYXNWhNpmK
    """
    type: str = "retrieval"

