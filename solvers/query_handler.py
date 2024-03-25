import re
import uuid
import networkx as nx
import time
import json
import sys
from variamos import query, model, rules
from utils import enums, uuid_utils
from utils import exceptions
from solvers import solver_control
from grammars import clif
from generators import uvl_clif_generator, vmos_clif_generator

class QueryHandler:
    query_obj: query.Query
    controller: solver_control.SolverController
    clif_model: clif.Text
    clif_str: str
    translation_rules: rules.Rules | None

    def __init__(
        self,
        # model_obj: model.Model,
        query_obj: query.Query,
        input: enums.InputEnum,
        nx_graph: nx.DiGraph | None = None,
        # clif_model: clif.Text,
        translation_rules: rules.Rules | None = None,
        model_str: str | None = None,
    ) -> None:
        # the query object is always the same
        self.query_obj = query_obj
        thread_time0 = time.thread_time_ns()
        ### Init should depend on the input type
        match input:
            case enums.InputEnum.vmos:
                self.nx_graph = nx_graph
                self.translation_rules = translation_rules
                # Construct the AST from the graph and the translation rules
                clif_gen = vmos_clif_generator.VMosCLIFGenerator(
                    rule_set=translation_rules,
                    variamos_graph=nx_graph,
                )
                self.clif_str = clif_gen.generate_logic_model()
                print("made clif model")
                thread_time1 = time.thread_time_ns()
                clif_model = self.create_clif_ast(
                    # rules=translation_rules, graph=nx_graph
                )
                print("parsed clif model")
                thread_time2 = time.thread_time_ns()
            case enums.InputEnum.uvl:
                self.model_str = model_str
                # Construct the AST from the UVL model
                clif_gen = uvl_clif_generator.UvlCLIFGenerator(
                    model_str=model_str
                )
                self.clif_str = f"(model {clif_gen.generate_logic_model()[0]} )"
                thread_time1 = time.thread_time_ns()
                clif_model = self.create_clif_ast()
                thread_time2 = time.thread_time_ns()
            case _:
                raise exceptions.QueryException("Unknown input type")
        # take the time to build the model
        self.clif_gen_time = thread_time1 - thread_time0
        self.clif_ast_time = thread_time2 - thread_time1
        # build the controller
        if self.query_obj.operation != query.OperationEnum.get_model:
            self.controller = solver_control.SolverController(
                target_lang=query_obj.solver,
                clif_model=clif_model,
                # vmos_model=model_obj,
                vmos_graph=nx_graph,
                translation_rules=translation_rules,
            )

    def create_clif_ast(self, 
        #rules: rules.Rules, graph: nx.DiGraph
    ):
        # clif_gen = vmos_clif_generator.VMosCLIFGenerator(
        #     rule_set=rules,
        #     # variamos_model=vmos_model,
        #     variamos_graph=graph,
        # )
        # self.clif_str = clif_gen.generate_logic_model()
        print(self.clif_str)
        clif_mm = clif.clif_meta_model()
        print(sys.getrecursionlimit())
        sys.setrecursionlimit(10**9)
        clif_model: clif.Text = clif_mm.model_from_str(self.clif_str)
        return clif_model

    def is_dry(self):
        return (
            self.query_obj.operation == query.OperationEnum.sat
            or self.query_obj.operation == query.OperationEnum.get_model
            or self.query_obj.operation == query.OperationEnum.get_code
        )

    def run_query(self):
    # def run_query(self, project_json, idx, feature_model):
        # there can either be iteration or not
        if (i_spec := self.query_obj.iterate_over) is not None:
            # This branch implies that we need to handle the iterative
            # execution of the solver
            # TODO: Check for empty iteration spec
            # TODO: Figure out how to connect deeply to the solver
            # TODO: Make sure we are covering the different cases of how the
            # vars are constructed
            return self.controller.run_iteration_operation(
                iteration_spec=i_spec
            )
        # If not handle the operation to be executed
        # Pydantic lets us assume all the other types are ok
        else:
            match self.query_obj.operation:
                case query.OperationEnum.sat:
                    return self.controller.sat()
                case query.OperationEnum.solve:
                    # FIXME: We do not yet handle multiple product lines
                    # FIXME: We have a problem handling model updates now...
                    # self.controller.update_model(
                    #     fm=feature_model,
                    #     rules=self.translation_rules,
                    #     result=self.controller.solve_one(),
                    # )
                    # project_json["productLines"][0]["domainEngineering"][
                    #     "models"
                    # ][idx] = json.loads(feature_model.json(by_alias=True))
                    # return project_json
                    return self.controller.solve_one()
                case query.OperationEnum.nsolve:
                    return self.controller.solve_n(self.query_obj.operation_n)
                case query.OperationEnum.get_model:
                    return self.pretty_model()
                case query.OperationEnum.get_code:
                    return self.controller.get_code()
                case query.OperationEnum.optimize:
                    # check that the query contains an optimization target
                    if self.query_obj.optimization_target is None:
                        raise exceptions.QueryException(
                            "No optimization target specified"
                        )
                    if self.query_obj.optimization_direction not in [
                        query.OptimizationDirectionEnum.min,
                        query.OptimizationDirectionEnum.max,
                    ]:
                        raise exceptions.QueryException(
                            "Invalid optimization target specified"
                        )
                    optim_result = self.controller.optimize(
                        objective=self.query_obj.optimization_target,
                        direction=self.query_obj.optimization_direction,
                    )
                    return optim_result

    def pretty_model(self):
        regex = re.compile(r"(UUID(?:_[a-f0-9]+){5})")
        result_str = self.clif_str[:]
        for occ in re.findall(regex, self.clif_str):
            occ_clean: str = occ.replace("UUID_", "")
            uuid_str = uuid_utils.to_uuid_from_underscore(occ_clean)
            found = True
            try:
                element: model.Element = self.nx_graph.nodes.data("element")[
                    uuid_str
                ]
                result_str = result_str.replace(occ, element.name)
            except KeyError:
                found = False
            if not found:
                for _, elem in list(self.nx_graph.nodes.data("element")):
                    for prop in elem.properties:
                        if prop["custom"]:
                            if uuid.UUID(prop["id"]) == uuid_str:
                                print(
                                    "Replacing ",
                                    occ,
                                    " with ",
                                    elem.name + "::" + prop["name"],
                                )
                                result_str = result_str.replace(
                                    occ, elem.name + "::" + prop["name"]
                                )
        print(result_str)
        return result_str
    
    def get_statistics(self):
        stats = {
            "clif_gen_time": self.clif_gen_time,
            "clif_ast_time": self.clif_ast_time,
            "bridge_solve_time": self.controller.bridge_solve_time,
            "code_gen_time": self.controller.code_gen_time,
            "generic_csp_model_time": self.controller.generic_csp_time,
            "concrete_csp_model_time": self.controller.constraint_model_time,
            "n_constraints": self.controller.n_constraints,
            "n_features": self.controller.n_features,
        }
        print(json.dumps(stats, indent=4))
        return stats
