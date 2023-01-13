import networkx as nx
from grammars.clif import Text
from targets.minzinc.minizinc_bridge import MiniZincBridge
from targets.minzinc.minizinc_model import clif_to_MZN
from targets.solver_model import SolverModel
from targets.swi.prolog_bridge import SWIBridge
from targets.swi.swi_model import clif_to_SWI
from utils.enums import TargetLang
from utils import exceptions
from variamos import query, model, rules


class SolverController:
    """A class defining a unified control mechanism for the solvers.

    Attributes:
        target_lang (str):
    """

    constraint_model: SolverModel

    def __init__(
        self,
        target_lang,
        clif_model: Text,
        vmos_model: model.Model,
        vmos_graph: nx.DiGraph,
        translation_rules: rules.Rules,
    ) -> None:
        self.vmos_model = vmos_model
        self.vmos_graph = vmos_graph
        self.translation_rules = translation_rules
        self.target_lang = target_lang
        match target_lang:
            case TargetLang.minizinc:
                self.constraint_model = clif_to_MZN(clif_model)
                self.bridge = MiniZincBridge()
            case TargetLang.swi:
                self.constraint_model = clif_to_SWI(clif_model)
                self.bridge = SWIBridge()
            case _:
                raise TypeError("Language unsupported")

    def _run_fixed_sat(
        self, elem_sel: query.ModelSelectorSpec, iter_results: list, var_id: str
    ):
        self.constraint_model.fix_variable(
            variable=var_id,
            # We ignore to supress none warning since we have its presence
            # guaranteed
            value=elem_sel.with_value,  # pyright: ignore
        )
        iter_results.append(self.sat())
        self.constraint_model.reset_fix(variable=var_id)

    def _run_element_iteration(self, elem_sel: query.ModelSelectorSpec):
        # Find all matching elements and iterate over them
        iter_results = []
        for selected_element in filter(
            lambda elem: elem.type in elem_sel.object_type,
            self.vmos_model.elements,
        ):
            var_id = "UUID_" + model.to_underscore_from_uuid(
                selected_element.id
            )
            self._run_fixed_sat(elem_sel, iter_results, var_id)
        return iter_results

    # TODO: Refactor to avoid duplication of code
    def _run_relationship_element_iteration(
        self, elem_sel: query.ModelSelectorSpec
    ):
        iter_results = []
        # If there is a lookup rule for the type
        # use it
        if "type" in (
            schema := self.translation_rules.relation_property_schema
        ):
            # use the lookup schema to determine how to access it from the
            # properties
            type_schema = schema["type"]
            idx, key = type_schema.index, type_schema.key
            try:
                # loop over the relationships to get the elements to iterate
                # over, making sure to only consider those that have
                # properties to access
                for rel in filter(
                    lambda r: len(r.properties) > 0,
                    self.vmos_model.relationships,
                ):
                    relationship_type = rel.properties[idx][key]
                    if relationship_type in elem_sel.object_type:
                        element_id = "UUID_" + model.to_underscore_from_uuid(
                            # We'll assume that the relation connections are
                            # in fact present
                            rel.target_id  # pyright: ignore
                            if elem_sel.relationship_element == "target"
                            else rel.source_id  # pyright: ignore
                        )
                        self._run_fixed_sat(
                            elem_sel, iter_results, var_id=element_id
                        )
            # FIXME: Make sure we handle these cases correctly
            except IndexError:
                raise IndexError
            except KeyError:
                raise KeyError
        else:
            # TODO: Refactor this to avoid duplication
            for rel in self.vmos_model.relationships:
                relationship_type = rel.type
                if relationship_type in elem_sel.object_type:
                    element_id = "UUID_" + model.to_underscore_from_uuid(
                        # We'll assume that the relation connections are
                        # in fact present
                        rel.target_id  # pyright: ignore
                        if elem_sel.relationship_element == "target"
                        else rel.source_id  # pyright: ignore
                    )
                    self._run_fixed_sat(
                        elem_sel, iter_results, var_id=element_id
                    )
        return iter_results

    def _run_reified_element_iteration(self, elem_sel: query.ModelSelectorSpec):
        # Iterate only over the elements that reify relations
        # First check if there is schema to determine the type from a
        # property
        iter_results = []
        if "type" in (
            schema := self.translation_rules.relation_reification_property_schema
        ):
            type_schema = schema["type"]
            idx, key = type_schema.index, type_schema.key
            try:
                # Do a complex filter for only the reified elements that
                # are of a reifying type and that have the right property
                # derived type for the iteration selector
                for reif in filter(
                    lambda elem: elem.type
                    in self.translation_rules.relation_reification_types
                    and elem.properties[idx][key] in elem_sel.object_type,
                    self.vmos_model.elements,
                ):
                    # Now we must loop over the elements that go either in or
                    # out depending on whether we are looking at sources or
                    # targets
                    edges = list(
                        self.vmos_graph.out_edges(reif.id)
                        if elem_sel.relationship_element == "target"
                        else self.vmos_graph.in_edges(reif.id)
                    )
                    tuple_idx = (
                        1 if elem_sel.relationship_element == "target" else 0
                    )
                    node_uuids: list[str] = [
                        "UUID_"
                        + model.to_underscore_from_uuid(edge_tuple[tuple_idx])  # pyright: ignore
                        for edge_tuple in edges
                    ]
                    for id in node_uuids:
                        self._run_fixed_sat(elem_sel, iter_results, var_id=id)
            # FIXME: Make sure we handle these cases correctly but they should
            # not happen in principle
            except IndexError:
                raise IndexError
            except KeyError:
                raise KeyError
        else:
            for reif in filter(
                lambda elem: elem.type
                in self.translation_rules.relation_reification_types
                and elem.type in elem_sel.object_type,
                self.vmos_model.elements,
            ):
                # Now we must loop over the elements that go either in or
                # out depending on whether we are looking at sources or
                # targets
                edges = list(
                    self.vmos_graph.out_edges(reif.id)
                    if elem_sel.relationship_element == "target"
                    else self.vmos_graph.in_edges(reif.id)
                )
                tuple_idx = (
                    1 if elem_sel.relationship_element == "target" else 0
                )
                node_uuids: list[str] = [
                    "UUID_"
                    + model.to_underscore_from_uuid(edge_tuple[tuple_idx])  # type: ignore
                    for edge_tuple in edges
                ]
                for id in node_uuids:
                    self._run_fixed_sat(elem_sel, iter_results, var_id=id)
        return iter_results

    def run_iteration_operation(self, iteration_spec: query.IterationSpec):
        iteration_result = []
        for elem_sel in iteration_spec:
            if elem_sel.with_value is None:
                raise exceptions.QueryException("Missing iteration value")
            match elem_sel.model_object:
                case query.ModelObjectEnum.element:
                    iteration_result.extend(
                        self._run_element_iteration(elem_sel)
                    )
                case query.ModelObjectEnum.relationship:
                    # TODO: Implement this
                    raise NotImplementedError
                case query.ModelObjectEnum.relationship_element:
                    iteration_result.extend(
                        self._run_relationship_element_iteration(elem_sel)
                    )
                case query.ModelObjectEnum.reified:
                    iteration_result.extend(
                        self._run_reified_element_iteration(elem_sel)
                    )
        return iteration_result

    def set_iteration_variable_fix(self, value):
        pass

    # For now we will work under the assumption that the value is an integer
    def sat_with_value(self, variable: str, value: int):
        self.constraint_model.fix_variable(variable, value)
        return self.sat()

    def sat(self) -> bool:
        try:
            self.solve_one()
            return True
        except exceptions.SolverException:
            return False

    def solve_one(self):
        return self.solve_n(1)

    def solve_n(self, n_sols):
        # Maybe improve the api to make the typecheck pass
        return self.bridge.solve(self.constraint_model, n_sols)

    def update_model(self, fm, rules, result):
        self.bridge.update_model(fm, rules, result)

    # def do_query(self, query: Query):
    #     if query.n_sols > 0:
    #         result = self.solve(query.n_sols)
    #         query.v_to_bind[query.sol_var] = result