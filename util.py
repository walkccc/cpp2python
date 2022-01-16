import re
from typing import List


def get_py_type(cpp_type: str) -> str:
  if cpp_type == 'void':
    return 'None'
  if cpp_type == 'char':
    return 'str'
  if cpp_type == 'double':
    return 'float'
  if cpp_type == 'long':
    return 'int'
  if cpp_type == 'string':
    return 'str'
  if cpp_type.startswith('deque<'):
    return 'deque'
  if cpp_type.startswith('vector<'):
    m = re.match('vector<(.*)>', cpp_type)
    sub_py_type: str = get_py_type(m.group(1))
    return f'List[{sub_py_type}]'
  if cpp_type.startswith('unordered_set<'):
    m = re.match('unordered_set<(.*)>', cpp_type)
    sub_py_type: str = get_py_type(m.group(1))
    return f'Set[{sub_py_type}]'
  if cpp_type.startswith('unordered_map<'):
    m = re.match('unordered_map<(.*)>', cpp_type)
    key, value = m.group(1).split(', ', 1)
    return f'Dict[{get_py_type(key)}, {get_py_type(value)}]'
  if cpp_type.endswith('*'):
    return f'Optional[{get_py_type(cpp_type[:-1])}]'
  return cpp_type  # 'int'


def tokenize(cpp_params: str) -> List[str]:
  tokens: List[str] = []
  bracket_count = 0
  prev = 0
  for i, c in enumerate(cpp_params):
    if c == '<':
      bracket_count += 1
    elif c == '>':
      bracket_count -= 1
    elif c == ',' and bracket_count == 0:
      tokens.append(cpp_params[prev:i])
      prev = i + 2
  return tokens + [cpp_params[prev:]]
