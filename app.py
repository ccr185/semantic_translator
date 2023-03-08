"""
VariaMos semantic translator server.

By: Camilo Correa Restrepo camilo.correa-restrepo@univ-paris1.fr
By: Hiba Hnaini _@_.fr
"""

import json
from flask import Flask, request, jsonify, make_response
from variamos import model, transform
from solvers import query_handler
from utils.exceptions import SolverException

app = Flask(__name__)


# POST /sat
# POST /sol
# POST /nsol/

# POST /query
# Body: {"operation":"sat","iterate_over":["Abstract","Concrete"],"with_value":1}
# Body: {"optional":{"target":true,"rel_type": "Optional"},"operation":"sat","iterate_over":["optional"],"with_value":1 }


@app.route("/query", methods=["POST", "OPTIONS"])
def translate():
    if request.method == "OPTIONS":
        return _build_cors_preflight_response()
    elif request.method == "POST":
        """Handle a translation request for a given <language>."""
        content = request.json
        # print(content['data']['project'])
        # print(content['data']["rules"])
        selectedModel = content["data"]["modelSelectedId"]  # pyright: ignore
        # dry = request.headers.get("dry") == "true"
        (
            model,
            graph,
            rules,
            query,
            model_idx,
        ) = transform.transform_request_to_python(
            project_json=content["data"]["project"],  # pyright: ignore
            rules_json=content["data"]["rules"],  # pyright: ignore
            query_json=content["data"]["query"],  # pyright: ignore
            selectedModelId=selectedModel,
        )
        qh = query_handler.QueryHandler(
            nx_graph=graph,
            query_obj=query,
            translation_rules=rules,
        )
        try:
            return construct_response(qh, content, model_idx, model)
        except SolverException as err:
            print(err)
            return _corsify_actual_response(
                jsonify({"data": {"error": str(err)}})
            )
        # except BaseException as err:
        #     print(err)
        #     return _corsify_actual_response(
        #         jsonify({"data": {"error": "Cannot find configuration"}})
        #     )
    else:
        raise RuntimeError(
            "Weird - don't know how to handle method {}".format(request.method)
        )


def construct_response(
    qh: query_handler.QueryHandler, content, model_idx: int, model: model.Model
):
    # TODO: handle the different types of queries in the responses to avoid
    # always updating the model and updating the project JSON
    query_result = qh.run_query(
        project_json=content["data"]["project"],
        idx=model_idx,
        feature_model=model,
    )
    # update the model with the new values
    model.update_selections(query_result)
    # fix the project JSON content
    # get the lenght of the models
    dom_length = len(
        content["data"]["project"]["productLines"][0]["domainEngineering"][
            "models"
        ]
    )
    model = json.loads(model.json(by_alias=True))
    if model_idx < dom_length:
        content["data"]["project"]["productLines"][0]["domainEngineering"][
            "models"
        ][model_idx] = model
    else:
        content["data"]["project"]["productLines"][0]["applicationEngineering"][
            "models"
        ][model_idx - dom_length] = model
    return _corsify_actual_response(
        jsonify({"data": {"content": content["data"]["project"]}})
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
