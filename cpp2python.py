import os.path
import re
import sys
from typing import List, Tuple

import keywords
import util


def remove_cpp_keywords(cpp_param: str) -> str:
  return cpp_param \
      .replace('&', '') \
      .replace('&&', '') \
      .replace('const ', '') \
      .replace('auto ', '')


def get_py_params(cpp_params: str) -> str:
  py_params: List[str] = []
  for cpp_param in util.tokenize(cpp_params):
    cpp_type, var = remove_cpp_keywords(cpp_param).rsplit(' ', 1)
    py_params.append(f'{var}: {util.get_py_type(cpp_type)}')
  return ', '.join(py_params)


def modify_initialize_constructor(m: Tuple[str, str]) -> str:
  leading_spaces, _, cpp_params, initialized_vars = m
  if not cpp_params:
    return f'{leading_spaces}def __init__(self):\n{leading_spaces}  self.'
  return f'{leading_spaces}def __init__(self, {get_py_params(cpp_params)}):\n{leading_spaces}  self.{initialized_vars}'


def modify_constructor(m: Tuple[str, str, str]) -> str:
  leading_spaces, _, cpp_params = m
  if not cpp_params:
    return f'{leading_spaces}def __init__(self):'
  return f'{leading_spaces}def __init__(self, {get_py_params(cpp_params)}):'


def modify_method(m: Tuple[str, str, str]) -> str:
  cpp_type, func_name, cpp_params = m
  if not cpp_params:
    return f'def {func_name}(self) -> {util.get_py_type(cpp_type)}:'
  return f'def {func_name}(self, {get_py_params(cpp_params)}) -> {util.get_py_type(cpp_type)}:'


def modify_range_for_loop(m: Tuple[str, str]) -> str:
  var, iterable = m
  var = remove_cpp_keywords(var) \
      .replace('string ', '') \
      .replace('int ', '') \
      .replace('char ', '')
  if var.startswith('[_') and var.endswith(']'):
    value = var[2:-1].split(', ')[1]
    return f'for {value} in {iterable}.values():'
  if var.startswith('[') and var.endswith(']'):
    key, value = var[1:-1].split(', ')
    return f'for {key}, {value} in {iterable}.items():'
  return f'for {var} in {iterable}:'


def modify_index_for_loop(m: Tuple[str, str, str, str, str, str]) -> str:
  i_start, start_val, i_end, sign, end, steps = m

  offset = 0
  end = re.sub(r'(\w+).length\(\)', r'len(\1)', end)
  end = re.sub(r'(\w+).size\(\)', r'len(\1)', end)
  if ' + ' in i_end:
    offset -= int(i_end.split(' + ')[1])
  if sign == '<=':
    offset += 1
  elif sign == '>=':
    offset -= 1

  if end == '0':
    end = str(offset)
  elif offset < 0:
    end += ' - ' + str(offset).split('-')[1]
  elif offset > 0:
    end += ' + ' + str(offset)

  pysteps = ''
  if steps.startswith('++'):
    pysteps = ''
  elif steps.startswith('--'):
    pysteps = ', -1'
  elif ' += ' in steps:
    pysteps = f", {steps.split(' += ')[1]}"
  elif ' -= ' in steps:
    pysteps = f", -{steps.split(' -= ')[1]}"

  if start_val == '0' and not pysteps:
    return f'for {i_start} in range({end}):'
  return f'for {i_start} in range({start_val}, {end}{pysteps}):'


def modify_substr(m: Tuple[str, str, str]) -> str:
  var, start, end = m
  tokens = end.split(' ')
  if len(tokens) == 1:
    if start == '0':
      return f'{var}[:{end}]'
    return f'{var}[{start}:{start} + {end}]'
  if len(tokens) == 5 and tokens[1] == '-' and tokens[2] == start and \
          tokens[3] == '+' and tokens[4] == '1':
    return f'{var}[{start}:{tokens[0]} + 1]'
  return f'{var}[{start}:???]'


def modify_ternary(m: Tuple[str, str, str]) -> str:
  prefix, after_equal, a, b = m
  if '(' in after_equal:
    statement, cond = after_equal.split('(', 1)
    if '+' in statement or '-' in statement:
      return f'{prefix} {statement}({a} if {cond} else {b})'
    return f'{prefix} {statement}{a} if {cond} else {b}'
  return f'{prefix} {a} if {after_equal} else {b}'


def modify_map(m: Tuple[str, str, str]) -> str:
  key_type, value_type, var = m
  if value_type == 'int':
    return f'{var} = collections.Counter()'
  if value_type.startswith('vector<'):
    return f'{var} = collections.defaultdict(list)'
  if value_type.startswith('unordered_set<'):
    return f'{var} = collections.defaultdict(set)'


def substitute(line: str) -> str:
  for access_modifier in ['public:', 'private:']:
    if access_modifier in line:
      return ''

  for k, v in keywords.replaced_start.items():
    line = line.replace(k, v)

  """ -vector<vector<pair<int, int>>> graph(n);
      +graph = [[] for _ in range(n)]
  """
  line = re.sub(r'vector<vector<pair<\w+, \w+>>> (\w+)\((\w+)\);',
                r'\1 = [[] for _ in range(\2)]', line)

  """ -MyClass(int n) : var(n, -1) {}
      +def __init__(self, n: int):
      +  self.var = [-1] * n
  """
  line = re.sub(r'^(\s*)(\w+)\((.*)\) : (.*) {?',
                lambda m: modify_initialize_constructor(m.groups()),
                line)

  """ -MyClass(const vector<int>& v1) {
      +def __init__(self, v1: List[int]):
  """
  line = re.sub(r'^(\s*)(\w+)\((.*)\) {',
                lambda m: modify_constructor(m.groups()),
                line)

  """ -void myFunc(const string& param1, bool param2) {
      +def myFunc(param1: str, param2: bool) -> None:
  """
  line = re.sub(r'([\w<>\*]+) (\w+)\((.*)\) {',
                lambda m: modify_method(m.groups()),
                line)

  """ -for (const vector<int>& edge : edges) {
      +for u, v in edges:
  """
  line = re.sub(r'for \(const vector<int>& edge : edges\) \{',
                r'for u, v in edges:', line)

  """ -for (const vector<int>& row : grid)
      +for row in grid:
  """
  line = re.sub(r'for \((?:const )?vector<int>& (\w+) : (\w+)\)',
                r'for \1 in \2:', line)

  """ -const int u = edge[0];
      +
  """
  line = re.sub(r'const int u = edge\[0\];', '', line)

  """ -const int v = edge[1];
      +
  """
  line = re.sub(r'const int v = edge\[1\];', '', line)

  """ -graph[u].emplace_back(v, vals[v])
      +graph[u].append((v, vals[v]))
  """
  line = re.sub(r'(\w+)\[(\w+)\]\.emplace_back\(([^,]+), ([^)]+)\);',
                r'\1[\2].append((\3, \4))', line)

  """ -for (const auto& s : dfs(words, 0)) {
      +for s in dfs(words, 0):
  """
  line = re.sub(r'for \((.*) : (.*)\)[ {]*',
                lambda m: modify_range_for_loop(m.groups()),
                line)

  """ -for (int i = 0; i < s.length(); ++i)
      +for i in range(len(s)):

      -for (size_t i = s.length() - 1; i >= 0; i -= 3) {
      +for i in range(len(s) - 1, -1, -3):

      -for (int i = 1; i + 2 <= s.length(); i += 2) {
      +for i in range(1, len(s) - 1, 2):
  """
  line = re.sub(r'for \(\w+ (\w+) = ([^;]+); ([\w +-]*) (<|<=|>|>=) ([^;]+); ([^)]+)\)[ {]*',
                lambda m: modify_index_for_loop(m.groups()),
                line)

  """ -s.substr(start, end - start + 1)
      +s[start:end]
  """
  line = re.sub(r'(\w+)\.substr\((\w+), ([^)]*)\)',
                lambda m: modify_substr(m.groups()), line)

  """ -s.substr(start)
      +s[start:]
  """
  line = re.sub(r'(\w+)\.substr\(([^)]*)\)', r'\1[\2:]', line)

  """ -UF uf(m * n);
      +uf = UF(m * n)
  """
  line = re.sub(r'([A-Z]\w*) (\w+)\((.*)\);', r'\2 = \1(\3)', line)

  """ -statement = var + ((cond) ? a : b);
      +statement = var + a if (cond) else b

  """
  line = re.sub(r'(return|\+|=) \(?([^)]*)\)? \? (.*) : (.*);',
                lambda m: modify_ternary(m.groups()),
                line)

  """ -unordered_map<char, int> count;
      +count = Counter()
  """
  line = re.sub(r'unordered_map<(\w+), ([\w<>]+)> (\w+);',
                lambda m: modify_map(m.groups()),
                line)

  """ -auto [a, b]
      +a, b
  """
  line = re.sub(r'auto \[([^]]*)\]', r'\1', line)

  """ -class MyClass {
      +class MyClass:
  """
  line = re.sub(r'class (\w+) {', r'class \1:', line)

  """ -!graph.count(u)
      +u not in graph
  """
  line = re.sub(r'!(\w+)\.count\((\w+)\)', r'\2 not in \1', line)

  """ -graph.count(u)
      +u in graph
  """
  line = re.sub(r'(\w+)\.count\((\w+)\)', r'\2 in \1', line)

  """ -string var;
      +var = ''
  """
  line = re.sub(r'string (\w+);', r"\1 = ''", line)

  """ -++var;
      +var += 1
  """
  line = re.sub(r'\+{2}([^;]+);', r'\1 += 1', line)

  """ ---var;
      +var -= 1
  """
  line = re.sub(r'\-{2}([^;]+);', r'\1 -= 1', line)

  """ -!A.empty()
      +A
  """
  line = re.sub(r'!(\w+)\.empty\(\)', r'\1', line)

  """ -A.empty()
      +not A
  """
  line = re.sub(r'(\w+)\.empty\(\)', r'not \1', line)

  """ -move(A)
      +A
  """
  line = re.sub(r'move\((\w+)\)', r'\1', line)

  """ -to_string(A)
      +str(A)
  """
  line = re.sub(r'to_string\((\w+)\)', r'str(\1)', line)

  """ -stoi(s)
      +int(s)
  """
  line = re.sub(r'stoi\((\w+)\)', r'int(\1)', line)

  """ -stol(s)
      +int(s)
  """
  line = re.sub(r'stol\((\w+)\)', r'int(\1)', line)

  """ -vector<vector<int>> A(m, vector<int>(n));
      +A = [[0] * n for _ in range(m)]
  """
  line = re.sub(r'vector<vector<int>> (\w+)\((\w+), vector<int>\((\w+)\)\);',
                r'\1 = [[0] * \3 for _ in range(\2)]',
                line)

  """ -vector<vector<bool>> A(m, vector<bool>(n));
      +A = [[0] * n for _ in range(m)]
  """
  line = re.sub(r'vector<vector<bool>> (\w+)\((\w+), vector<bool>\((\w+)\)\);',
                r'\1 = [[False] * \3 for _ in range(\2)]',
                line)

  """ -vector<int> A;
      +A = []
  """
  line = re.sub(r'vector<[^>]+>+ (\w+);', r'\1 = []', line)

  """ -vector<int> A(B.size());
      +[0] * B.size()
  """
  line = re.sub(r'vector<[^>]+>+ (\w+)\((.*)\);', r'\1 = [0] * \2', line)

  """ -vector<int>(B.size())
      +[0] * B.size()
  """
  line = re.sub(r'vector<[^>]+>+\((.*)\)', r'[0] * \1', line)

  """ -vector<int> A{1, 2};
      +A = [1, 2]
  """
  line = re.sub(r'vector<\S+> (\w+)\{([^}]*)\};', r'\1 = [\2]', line)

  """ -stack<int> A;
      +A = []
  """
  line = re.sub(r'stack<[^>]+>+ (\w+)', r'\1 = []', line)

  """ -unordered_set<char> seen;
      +seen = set()
  """
  line = re.sub(r'unordered_set<[^>]+> (\w+);', r'\1 = set()', line)

  """ -deque<int> q;
      +q = deque()
  """
  line = re.sub(r'deque<[^>]+>+ (\w+);', r'\1 = deque()', line)

  """ -queue<int> q;
      +q = deque()
  """
  line = re.sub(r'^\s+queue<.*> (\w+);', r'\1 = deque()', line)

  """ -queue<pair<TreeNode*, int>> q{{{root, 1}}};
      +q = deque([(root, q)])
  """
  line = re.sub(
      r'queue<[^>]+>+ (\w+){+(\w+), (\w+)}+;', r'\1 = deque([(\2, \3)])', line)

  """ -{"0", "1", "2"}
      +["0", "1", "2"]
  """
  line = re.sub(r'{(.*)}', r'[\1]', line)

  """ -!cond
      +not cond
  """
  line = re.sub('!([^=\n])', 'not \\1', line)

  """ -A.length()
      +len(A)
  """
  line = re.sub(r'(\S+).length\(\)', r'len(\1)', line)

  """ -A.size()
      +len(A)
  """
  line = re.sub(r'(\S+).size\(\)', r'len(\1)', line)

  """ -if (cond)
      +if cond:
  """
  line = re.sub(r'(^\s*)if \((.*)\)[ {]*', r'\1if \2:', line)

  """ -} else if (cond)
      +elif cond:

      -else if (cond)
      +elif cond:
  """
  line = re.sub(r'(} )?else if \((.*)\)$', r'elif \2:', line)

  """ -else {
      +else:

      -} else {
      +else:
  """
  line = re.sub(r'^(\s*)}?\s?else(?:\s{)?', r'\1else:', line)

  """ -while (cond)
      +while cond:
  """
  line = re.sub(r'while \((.*)\)', r'while \1:', line)

  """ -sort(begin(A), end(A));
      +A.sort()
  """
  line = re.sub(r'sort\(begin\((\w+)\), end\(\w+\)\);', r'\1.sort()', line)

  """ -reverse(begin(A), end(A));
      +A.reverse()
  """
  line = re.sub(r'reverse\(begin\((\w+)\), end\(\w+\)\);',
                r'\1.reverse()', line)

  """ -*min_element(begin(A), end(A));
      +min(A)
  """
  line = re.sub(r'\*min_element\(begin\((.*)\), end\((\w|.)+\)\);',
                r'min(\1)', line)

  """ -*max_element(begin(A), end(A));
      +max(A)
  """
  line = re.sub(r'\*max_element\(begin\((.*)\), end\((\w|.)+\)\);',
                r'max(\1)', line)

  """ -accumulate(begin(A), end(A), 0);
      +sum(A)
  """
  line = re.sub(r'accumulate\(begin\((.*)\), end\((\w|.)+\), [^)]*\);',
                r'sum(\1)', line)

  """ -priority_queue<int, vector<int>, greater<>> minHeap;
      +minHeap = []
  """
  line = re.sub(r'priority_queue<int, vector<int>, greater<>> (\w+);',
                r'\1 = []', line)

  """ -priority_queue<int> maxHeap;
      +Queue<Integer> maxHeap = new PriorityQueue<>(Collections.reverseOrder());
  """
  line = re.sub(r'priority_queue<.*> (\w+);',
                r'\1 = []', line)

  """ -maxHeap.push(val);
      +heapq.heappush(maxHeap, val)
  """
  line = re.sub(r'(\w+)\.push\(([^)]+)\);',
                r'heapq.heappush(\1, \2)', line)

  """ -maxHeap.top(), maxHeap.pop();
      +heapq.heappop(maxHeap)
  """
  line = re.sub(r'(\w+)\.top\(\), \w+\.pop\(\);',
                r'heapq.heappop(\1)', line)

  for k, v in keywords.replaced_end.items():
    line = line.replace(k, v)

  for useless_keyword in keywords.useless:
    line = line.replace(useless_keyword, '')

  return line


def process_file(in_filename: str, out_filename: str) -> None:
  with open(in_filename, 'r', encoding='utf-8') as f:
    lines = f.readlines()  # probably would die on sources more than 100 000 lines :D
  with open(out_filename, 'w+', encoding='utf-8') as f:
    for line in lines:
      f.write(substitute(line))


if __name__ == '__main__':
  if len(sys.argv) != 2:
    sys.exit(-1)

  if not os.path.isfile(sys.argv[1]):
    print('Not a file or directory', sys.argv[1], file=sys.stderr)
    sys.exit(-1)

  in_filename = sys.argv[1]  # 'abc123.cpp'

  process_file(in_filename, in_filename.split('.cpp')[0] + '.py')
