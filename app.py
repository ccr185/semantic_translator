"""
VariaMos semantic translator server.

By: Camilo Correa Restrepo camilo.correa-restrepo@univ-paris1.fr
By: Hiba Hnaini _@_.fr
"""

from flask import Flask, request, jsonify, make_response
from main import run, SolverException

app = Flask(__name__)


@app.route("/translate/<language>", methods=["POST", "OPTIONS"])
@app.route("/translate/<language>/<solver>", methods=["POST", "OPTIONS"])
def translate(language, solver="minizinc"):
    if request.method == "OPTIONS":
        return _build_cors_preflight_response()
    elif request.method == "POST":
        """Handle a translation request for a given <language>."""
        content = request.json
        # print(content['data']['project'])
        # print(content['data']["rules"])
        selectedModel = content["data"]["modelSelectedId"]  # pyright: ignore
        dry = request.headers.get("dry") == "true"
        try:
            return _corsify_actual_response(
                jsonify(
                    {
                        "data": {
                            "content": run(
                                model=content["data"][  # pyright: ignore
                                    "project"
                                ],
                                rules=content["data"][  # pyright: ignore
                                    "rules"
                                ],
                                language=language,
                                solver=solver,
                                dry=dry,
                                selectedModelId=selectedModel,
                            )
                        }
                    }
                )
            )
        except SolverException as err:
            print(err)
            return _corsify_actual_response(
                jsonify({"data": {"error": str(err)}})
            )
        except BaseException as err:
            print(err)
            return _corsify_actual_response(
                jsonify({"data": {"error": "Cannot find configuration"}})
            )
    else:
        raise RuntimeError(
            "Weird - don't know how to handle method {}".format(request.method)
        )


def _build_cors_preflight_response():
    response = make_response()
    response.headers.add("Access-Control-Allow-Origin", "*")
    response.headers.add("Access-Control-Allow-Headers", "*")
    response.headers.add("Access-Control-Allow-Methods", "*")
    return response


def _corsify_actual_response(response):
    response.headers.add("Access-Control-Allow-Origin", "*")
    return response
