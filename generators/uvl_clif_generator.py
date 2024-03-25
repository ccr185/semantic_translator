from dataclasses import dataclass
from swiplserver import (
    PrologMQI,
    PrologThread,
    PrologResultNotAvailableError,
    create_posix_path,
)
import tempfile
import re
import uuid


@dataclass
class UvlCLIFGenerator:
    model_str: str

    def generate_logic_model(self):
        print(self.model_str)
        path = create_posix_path("generators/uvl_generator/ast.pl")
        with tempfile.NamedTemporaryFile(suffix=".uvl", delete=True) as f:
            f.write(self.model_str.encode())
            print(f.name)
            print("wrote model to file")
            f.flush()
            f.seek(0)
            uvl_path = create_posix_path(f.name)
            with PrologMQI() as mqi:
                with PrologThread(mqi) as prolog_thread:
                    prolog_thread.query(f"consult('{path}')")
                    # Now we have the CLIF String coming from the model
                    # However, our parser will not like quoted strings
                    # So we need to remove the quotes
                    parse_result = prolog_thread.query(
                        f"debug(parser), print_clif_from_ast('{uvl_path}', CLIFS)", 100
                    )
            print("Query Complete")
            if parse_result is False:
                raise PrologResultNotAvailableError()
            raw_clif_string = parse_result[0]["CLIFS"]
            regex = re.compile(r'(\"[^\r\n\".]+\")')
            expr_match_dict = {
                occ: f"UUID_{str(uuid.uuid4()).replace('-','_')}" 
                for occ in set(regex.findall(raw_clif_string))
            }
            clif_str = raw_clif_string
            for expr, replacement in expr_match_dict.items():
                clif_str = clif_str.replace(expr, replacement)
            return clif_str, expr_match_dict



            
