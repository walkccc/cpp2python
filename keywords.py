from typing import Dict, List

replaced_start: Dict[str, str] = {
    'class Solution {': 'class Solution:',
    '->': '.',
    '//': '#',
    '/': '//',
    'false': 'False',
    'true': 'True',
    '||': 'or',
    '"': '\'',
    '.push_back(': '.append(',
    '.emplace(': '.append(',
    '.pop_front(': '.popleft(',
    '.pop_back(': '.pop(',
    '.insert(': '.add(',
    '.erase(': '.remove(',
    '.front()': '[0]',
    '.back()': '[-1]',
    'INT_MAX': 'math.inf',
    'INT_MIN': '-math.inf',
    'nullptr': 'None'
}

replaced_end: Dict[str, str] = {
    '&&': 'and',
    '1\'000\'000\'007': '1_000_000_007',
    '.top()': '[-1]',
    '.push(': '.append(',
}

useless: List[str] = [
    'const ', 'constexpr ', 'string ', 'string& ', 'long ', 'int ', 'bool ',
    'char ', '++', '--', ';',  '}', '{',
]
