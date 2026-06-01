# parser.py
import re
import numpy as np
from utils import BASE_NAMESPACE, FUNCTION_PATTERN

class FunctionParser:
    def __init__(self, constants=None):
        self.constants = constants or {}
        self.functions = BASE_NAMESPACE.copy()
        self.func_pattern = FUNCTION_PATTERN

    def add_implicit_multiplication(self, expr, var):
        expr = expr.replace('^', '**')
        expr = re.sub(r'(\d+)(?=\()', r'\1*', expr)
        expr = re.sub(r'(' + var + r')(?=\()', r'\1*', expr, flags=re.IGNORECASE)
        expr = re.sub(r'(\))(?=\()', r'\1*', expr)
        expr = re.sub(r'(\d+)(?=(' + self.func_pattern + r')\()', r'\1*', expr, flags=re.IGNORECASE)
        expr = re.sub(r'(' + var + r')(?=(' + self.func_pattern + r')\()', r'\1*', expr, flags=re.IGNORECASE)
        expr = re.sub(r'(\))(?=(' + self.func_pattern + r')\()', r'\1*', expr, flags=re.IGNORECASE)
        expr = re.sub(r'(\d+)(?=' + var + r')', r'\1*', expr, flags=re.IGNORECASE)
        return expr

    def parse(self, func_str):
        used_constants = set()
        error_msg = None
        try:
            original = func_str
            func_str = func_str.replace(' ', '')

            is_implicit = False
            expr = func_str
            if func_str.lower().startswith('x='):
                is_implicit = True
                expr = func_str[2:].strip()
                if not expr:
                    return None, func_str, False, used_constants, "Пустое выражение"
                var = 'y'
            else:
                var = 'x'
                if func_str.lower().startswith('y='):
                    expr = func_str[2:].strip()
                elif func_str.lower().startswith('y ='):
                    expr = func_str[3:].strip()

            print(f"[DEBUG] Parse: {func_str}, var={var}, known_constants={set(self.constants.keys())}")
            identifiers = set(re.findall(r'\b[a-zA-Z]+\b', expr))
            print(f"[DEBUG] identifiers={identifiers}")
            reserved = set(['x', 'y', 'e', 'pi'] + list(self.functions.keys()))
            known_constants = set(self.constants.keys())

           
            used_constants.update(identifiers & known_constants)
            
            unknown = identifiers - reserved - known_constants
            if unknown:
                used_constants.update(unknown) 
            print(f"[DEBUG] used_constants={used_constants}")

            has_var = bool(re.search(r'\b' + var + r'\b', expr))

            if not has_var:
                if unknown:
                    error_msg = f"Неизвестные имена: {', '.join(unknown)}"
                    return None, expr, is_implicit, used_constants, error_msg
                namespace = {
                    '__builtins__': {},
                    'np': np,
                    **self.functions,
                    **{name: val['value'] for name, val in self.constants.items()}
                }
                try:
                    const_val = eval(expr, namespace)
                    if not isinstance(const_val, (int, float)):
                        raise ValueError(f"Не число: {const_val}")
                except Exception as e:
                    error_msg = f"Не удалось вычислить константу: {e}"
                    return None, expr, is_implicit, used_constants, error_msg
                func = lambda t: np.full_like(t, const_val, dtype=float)
                return func, expr, is_implicit, used_constants, None

            expr = self.add_implicit_multiplication(expr, var)
            namespace = {
                '__builtins__': {},
                'np': np,
                **self.functions,
                **{name: val['value'] for name, val in self.constants.items()}
            }
            lambda_str = f'lambda {var}: {expr}'
            code = compile(lambda_str, '<string>', 'eval')
            func = eval(code, namespace)

            test_t = np.array([0.0, 1.0])
            test_val = func(test_t)
            if not isinstance(test_val, np.ndarray):
                original_func = func
                func = lambda t: np.full_like(t, original_func(t))

            return func, expr, is_implicit, used_constants, None

        except Exception as e:
            error_msg = str(e)
            print(f"✗ Ошибка парсинга '{original}': {error_msg}")
            return None, func_str, False, used_constants, error_msg