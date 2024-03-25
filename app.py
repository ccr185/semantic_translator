"""
VariaMos semantic translator server.

By: 
By: 
"""

import json
import copy
import sys
from flask import Flask, request, jsonify, make_response, Response
from solvers.results import StatusEnum
from variamos import model, transform
from solvers import query_handler
from utils.exceptions import SolverException
from werkzeug.middleware.proxy_fix import ProxyFix
from utils import enums


app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

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
        # sys.setrecursionlimit(10**6)
        content = request.json
        # print(content['data']['project'])
        # print(content['data']["rules"])
        ## Now we need to handle queries that may come from other clients than just vmos
        if "input" in content["data"]:
            input = content["data"]["input"]
        else:
            input = enums.InputEnum.vmos
        match (input):
            # Case where the request comes from VariaMos
            case enums.InputEnum.vmos:
                selectedModel = content["data"]["modelSelectedId"]  # pyright: ignore
                # dry = request.headers.get("dry") == "true"
                (
                    model,
                    graph,
                    rules,
                    query,
                    model_idx,
                ) = transform.transform_vmos_request_to_python(
                    project_json=content["data"]["project"],  # pyright: ignore
                    rules_json=content["data"]["rules"],  # pyright: ignore
                    query_json=content["data"]["query"],  # pyright: ignore
                    selectedModelId=selectedModel,
                )
                qh = query_handler.QueryHandler(
                    nx_graph=graph,
                    query_obj=query,
                    translation_rules=rules,
                    input=input,
                )
            case enums.InputEnum.uvl:
                (query, model_str) = transform.transform_uvl_request_to_python(content)
                # Case where the request comes from UVL
                # We need to make a large refactor on the i/o side
                # to handle the different types of input languages
                qh = query_handler.QueryHandler(
                    query_obj=query,
                    model_str=model_str,
                    input=input,
                )
                model_idx = None
                model = None
            case _:
                return _corsify_actual_response(
                    jsonify({"data": {"error": "Unknown input type"}})
                )
        try:
            return construct_response(qh, content, model_idx, model)
        except SolverException as err:
            print(err)
            return _corsify_actual_response(jsonify({"data": {"error": str(err)}}))
        # except BaseException as err:
        #     print(err)
        #     return _corsify_actual_response(
        #         jsonify({"data": {"error": "Cannot find configuration"}})
        #     )
    else:
        # raise RuntimeError(
        #     "Weird - don't know how to handle method {}".format(request.method)
        # )
        # Return a 500 error, indicating that the server doesn't support this
        # method
        err_response = make_response(jsonify({"error": "Method not supported"}), 500)
        return _corsify_actual_response(err_response)


def construct_response(
    qh: query_handler.QueryHandler, content, model_idx: int, model: model.Model
):
    # TODO: handle the different types of queries in the responses to avoid
    # always updating the model and updating the project JSON
    query_result = qh.run_query(
        # project_json=content["data"]["project"],
        # idx=model_idx,
        # feature_model=model,
    )
    if qh.is_dry() or query_result is False:
        # In this case we know the response is a boolean
        return _corsify_actual_response(
            jsonify(
                {"data": {"content": query_result}, "statistics": qh.get_statistics()}
            )
        )
    elif (
        not isinstance(query_result, list)
        and query_result.status == StatusEnum.UNSATISFIED
    ):
        # In this case we know that no solution was foundx
        return _corsify_actual_response(
            jsonify({"data": {"content": False}, "statistics": qh.get_statistics()})
        )
    elif not query_result.solution.single_solution:
        # In this case we know the response is a list of configurations
        # HACK: FIXME: We will hack together the set of responses by creating a list
        # of project with the different configurations
        # This needs to be better handled in the future
        dom_length = len(
            content["data"]["project"]["productLines"][0]["domainEngineering"]["models"]
        )
        model_copies = []
        project_copies = []
        for sln in query_result.solution.solutions:
            m_c = model.copy(deep=True)
            m_c.update_selections(sln)
            model_copies.append(m_c)
            p_c = copy.deepcopy(content["data"]["project"])
            p_c["productLines"][0][
                (
                    "domainEngineering"
                    if model_idx < dom_length
                    else "applicationEngineering"
                )
            ]["models"][model_idx % dom_length] = json.loads(m_c.json(by_alias=True))
            project_copies.append(p_c)
        return _corsify_actual_response(
            jsonify(
                {"data": {"content": project_copies}, "statistics": qh.get_statistics()}
            )
        )
    elif query_result.solution.single_solution:
        # update the model with the new values
        model.update_selections(query_result.solution.solutions[0])
        # fix the project JSON content
        # get the lenght of the models
        dom_length = len(
            content["data"]["project"]["productLines"][0]["domainEngineering"]["models"]
        )
        model = json.loads(model.json(by_alias=True))
        if model_idx < dom_length:
            content["data"]["project"]["productLines"][0]["domainEngineering"][
                "models"
            ][model_idx] = model
        else:
            content["data"]["project"]["productLines"][0]["applicationEngineering"][
                "applications"
            ][0]["models"][model_idx - dom_length] = model
        return _corsify_actual_response(
            jsonify({"data": {"content": content["data"]["project"]}, "statistics": qh.get_statistics()})
        )
    else:
        raise RuntimeError("Unknown query result")


def _build_cors_preflight_response():
    response = make_response()
    response.headers.add("Access-Control-Allow-Origin", "*")
    response.headers.add("Access-Control-Allow-Headers", "*")
    response.headers.add("Access-Control-Allow-Methods", "*")
    return response


def _corsify_actual_response(response) -> Response:
    response.headers.add("Access-Control-Allow-Origin", "*")
    return response
