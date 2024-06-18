import json


def create_json(data: dict | list, path: str) -> None:
    with open(path, "w+") as json_file:
        json_file.write(json.dumps(data, indent=2, ensure_ascii=False))
