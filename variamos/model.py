import pydantic
import typing
import uuid
import networkx as nx

from utils import camel_handler


class Relationship(pydantic.BaseModel):
    id: uuid.UUID
    type: str
    name: str
    source_id: uuid.UUID
    target_id: uuid.UUID
    properties: list[dict[str, typing.Any]]
    # extra stuff
    points: list
    min: int
    max: int

    class Config:
        alias_generator = camel_handler.from_camelcase

    def to_nx_rel_attrs(self):
        return {"id": self.id, "properties": self.properties}


class Element(pydantic.BaseModel):
    id: uuid.UUID
    type: str
    name: str
    parent_id: typing.Optional[uuid.UUID]
    properties: list[dict[str, typing.Any]]
    # Visual components
    x: int
    y: int
    width: int
    height: int

    class Config:
        alias_generator = camel_handler.from_camelcase

    def to_nx_node_attrs(self):
        return {
            "type": self.type,
            "name": self.name,
            "parent_id": self.parent_id,
            "properties": self.properties,
        }


class Model(pydantic.BaseModel):
    id: uuid.UUID
    name: str
    elements: list[Element]
    relationships: list[Relationship]
    constraints: str = ""

    class Config:
        alias_generator = camel_handler.from_camelcase

    def construct_graph(self):
        G = nx.DiGraph(constraints=self.constraints)
        for e in self.elements:
            G.add_node(e.id, element=e)
        for r in self.relationships:
            G.add_edge(r.source_id, r.target_id, relation=r)
        return G


def to_underscore_from_uuid(id: uuid.UUID) -> str:
    return str(id).replace("-", "_")


def to_uuid_from_underscore(id: str) -> uuid.UUID:
    return uuid.UUID(id.replace("_", "-"))
