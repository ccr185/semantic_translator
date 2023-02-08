import re
import uuid
import networkx as nx
from variamos import query, model, rules
from utils import enums
from utils import exceptions
from solvers import solver_control
from grammars import clif
from generator import clif_generator


class QueryHandler:
    query_obj: query.Query
    controller: solver_control.SolverController
    clif_model: clif.Text
    clif_str: str
    translation_rules: rules.Rules

    def __init__(
        self,
        # model_obj: model.Model,
        nx_graph: nx.DiGraph,
        query_obj: query.Query,
        # clif_model: clif.Text,
        translation_rules: rules.Rules,
    ) -> None:
        self.nx_graph = nx_graph
        self.query_obj = query_obj
        self.translation_rules = translation_rules
        # Construct the AST from the graph and the translation rules
        clif_model = self.create_clif_ast(
            rules=translation_rules, graph=nx_graph
        )
        # build the controller
        if self.query_obj.operation != query.OperationEnum.get_model:
            self.controller = solver_control.SolverController(
                target_lang=query_obj.solver,
                clif_model=clif_model,
                # vmos_model=model_obj,
                vmos_graph=nx_graph,
                translation_rules=translation_rules,
            )

    def create_clif_ast(self, rules: rules.Rules, graph: nx.DiGraph):
        clif_gen = clif_generator.CLIFGenerator(
            rule_set=rules,
            # variamos_model=vmos_model,
            variamos_graph=graph,
        )
        self.clif_str = clif_gen.generate_logic_model()
        print(self.clif_str)
        clif_mm = clif.clif_meta_model()
        clif_model: clif.Text = clif_mm.model_from_str(self.clif_str)
        return clif_model

    def run_query(self, project_json, idx, feature_model):
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
                    self.controller.update_model(
                        fm=feature_model,
                        rules=self.translation_rules,
                        result=self.controller.solve_one(),
                    )
                    project_json["productLines"][0]["domainEngineering"][
                        "models"
                    ][idx] = feature_model
                    return project_json
                case query.OperationEnum.nsolve:
                    return len(
                        self.controller.solve_n(self.query_obj.operation_n)
                    )
                case query.OperationEnum.get_model:
                    return self.pretty_model()

    def pretty_model(self):
        regex = re.compile(r"(UUID(?:_[a-f0-9]+){5})")
        result_str = self.clif_str[:]
        for occ in re.findall(regex, self.clif_str):
            occ_clean: str = occ.replace("UUID_", "")
            uuid_str = model.to_uuid_from_underscore(occ_clean)
            found = True
            try:
                element: model.Element = self.nx_graph.nodes.data("element")[uuid_str]
                result_str = result_str.replace(occ, element.name)
            except KeyError:
                found = False
            if not found:
                for _, elem in list(self.nx_graph.nodes.data("element")):
                    for prop in elem.properties:
                        if prop["custom"]:
                            if uuid.UUID(prop["id"]) == uuid_str:
                                print("Replacing ", occ, " with ", elem.name + "::" + prop["name"])
                                result_str = result_str.replace(
                                    occ, elem.name + "::" + prop["name"]
                                )
        print(result_str)
        return result_str
