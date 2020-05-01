# Reads QPC files and returns a list of QPCBlocks

import os
from re import compile


def posix_path(string: str) -> str:
    return string.replace("\\", "/")


COND_OPERATORS = compile('(\\(|\\)|\\|\\||\\&\\&|>=|<=|==|!=|>|<)')


class QPCBlockBase:
    def __init__(self, file_path: str = ""):
        self.file_path = file_path
        self.items = []
    
    # temp stuff until i setup the rest for this later
    def __iter__(self):
        return self.items.__iter__()
    
    def __getitem__(self, item):
        return self.items[item]
    
    def extend(self, item):
        self.items.extend(item)
    
    def append(self, item):
        self.items.append(item)
    
    def remove(self, item):
        self.items.remove(item)
    
    def index(self, item):
        self.items.index(item)
    
    def to_string(self, quote_keys=False, quote_values=False, break_multi_value=False, break_on_key=False):
        final_string = ""
        for item in self.items:
            final_string += item.to_string(0, quote_keys, quote_values, break_multi_value, break_on_key) + "\n"
        return final_string
    
    def add_item(self, key: str, values: list, condition: str = "", line_num: int = 0):
        if type(values) == str:
            values = [values]
        sub_qpc = QPCBlock(self, key, values, condition, file_path=self.file_path, line_num=line_num)
        self.items.append(sub_qpc)
        return sub_qpc
    
    def add_item_index(self, index: int, key: str, values: list, condition: str = "", line_num: int = 0):
        sub_qpc = QPCBlock(self, key, values, condition, file_path=self.file_path, line_num=line_num)
        self.items.insert(index, sub_qpc)
        return sub_qpc
    
    def get_item(self, item_key):
        for item in self.items:
            if item.key == item_key:
                return item
        return None
    
    def get_item_values(self, item_key):
        for item in self.items:
            if item.key == item_key:
                return item.values
        return None
    
    def get_items(self, item_key):
        items = []
        for item in self.items:
            if item.key == item_key:
                items.append(item)
        return items
    
    # TODO: shorten these 4 function names?
    def get_items_condition(self, macros: list):
        items = []
        for item in self.items:
            if solve_condition(self, item.condition, macros):
                items.append(item)
        return items
    
    def get_item_keys_condition(self, macros: list):
        items = []
        for item in self.items:
            if solve_condition(self, item.condition, macros):
                items.append(item.key)
        return items
    
    def get_item_values_condition(self, macros: list):
        items = []
        for item in self.items:
            if solve_condition(self, item.condition, macros):
                items.extend(item.values)
        return items
    
    def get_item_list_condition(self, macros: list):
        items = []
        for item in self.items:
            if solve_condition(self, item.condition, macros):
                items.extend([item.key, *item.values])
        return items
    
    def get_keys_in_items(self):
        return [value.key for value in self.items]
    
    def get_item_index(self, qpc_item):
        try:
            return self.items.index(qpc_item)
        except IndexError:
            return None
        
    def print_info(self):
        print("unfinished qpc_reader.py QPCBlockBase.print_info()")


class QPCBlock(QPCBlockBase):
    def __init__(self, parent, key, values, condition: str = "", file_path: str = "", line_num: int = 0):
        super().__init__(file_path)
        self.parent = parent
        self.key = key
        self.values = values
        self.condition = condition
        self.line_num = line_num
    
    def to_string(self, depth=0, quote_keys=False, quote_values=False, break_multi_value=False, break_on_key=False):
        indent = "{0}".format(depth * '\t')
        index = self.parent.items.index(self)
        
        if quote_keys:
            string = "{0}\"{1}\"".format(indent, self.key)
        else:
            string = indent + self.key
        
        if break_on_key:
            key_indent = 0
        else:
            key_indent = len(self.key) - 1
        
        if self.values:
            for value_index, value in enumerate(self.values):
                if quote_values:
                    formatted_value = value.replace("'", "\\'").replace('"', '\\"')
                else:
                    formatted_value = value.replace("'", "\\'")
                    if formatted_value:
                        formatted_value = formatted_value[0] + \
                                          formatted_value[1:-1].replace('"', '\\"') + \
                                          formatted_value[-1]
                
                if quote_values:
                    string += " \"{0}\"".format(formatted_value)
                else:
                    string += " {0}".format(formatted_value)
                # untested
                if break_multi_value and value_index < len(self.values):
                    string += " \\\n{0}{1}".format(indent, " " * key_indent)
        
        if self.condition:
            string += " [" + add_spacing_to_condition(self.condition) + "]"
        
        if self.items:
            if 0 < index < len(self.parent.items):
                if not self.parent.items[index - 1].items:
                    string = "\n" + string
            
            string += "\n" + indent + "{\n"
            for item in self.items:
                string += item.to_string(depth + 1, quote_keys, quote_values, break_multi_value, break_on_key) + "\n"
            string += indent + "}"
            
            if index < len(self.parent.items) - 1:
                string += "\n"
        
        return string
    
    def get_list(self) -> tuple:
        return (self.key, *self.values)  # need parenthesis for python versions older than 3.8
    
    def solve_condition(self, macros: dict):
        return solve_condition(self, self.condition, macros)
    
    def invalid_option(self, *valid_option_list):
        print("WARNING: Invalid Option")
        print("\tValid Options:\n\t\t" + '\n\t\t'.join(valid_option_list))
        self.print_info()
    
    # would be cool if i could change the colors on this
    def fatal_error(self, message):
        print("FATAL ERROR: " + message)
        self.print_info()
        quit()
    
    # should Error and FatalError be the same?
    def error(self, message):
        print("ERROR: " + message)
        self.print_info()
    
    def warning(self, message):
        print("WARNING: " + message)
        self.print_info()
        
    def get_formatted_info(self) -> str:
        # TODO: this path is relative to the current directory
        final_string = f"\tFile Path: {self.file_path}\n"   \
                       f"\tLine: {str(self.line_num)}\n"    \
                       f"\tKey: {self.key}"
    
        if self.values:
            # if there is only one value, write it on the same line
            final_string += "\n\tValues:"
            final_string += f" {self.values[0]}" if len(self.values) == 1 else "\n\t\t" + '\n\t\t'.join(self.values)
                
        return final_string
    
    def print_info(self):
        print(self.get_formatted_info())


# maybe make a comment object so when you re-write the file, you don't lose comments
class Comment:
    def __init__(self):
        pass


def replace_macros_condition(split_string, macros):
    # for macro, macro_value in macros.items():
    for index, item in enumerate(split_string):
        if item in macros or item[1:] in macros:
            if str(item).startswith("!"):
                split_string[index] = str(int(not macros[item[1:]]))
            else:
                split_string[index] = macros[item]
        
        elif item.startswith("!"):
            split_string[index] = "1"
        
        elif item.startswith("$"):
            split_string[index] = "0"
    
    return split_string


def solve_condition(qpcblock: QPCBlockBase, condition: str, macros: dict) -> int:
    if not condition:
        return True
    
    solved_cond = condition
    # solve any sub conditionals first
    while "(" in solved_cond:
        sub_cond_line = (solved_cond.split('(')[1]).split(')')[0]
        sub_cond_value = solve_condition(qpcblock, sub_cond_line, macros)
        solved_cond = solved_cond.split('(', 1)[0] + str(sub_cond_value * 1) + solved_cond.split(')', 1)[1]
    
    split_string = COND_OPERATORS.split(solved_cond)
    
    solved_cond = replace_macros_condition(split_string, macros)
    
    if len(solved_cond) == 1:
        try:
            return int(solved_cond[0])
        except ValueError:
            return 1
    
    while len(solved_cond) > 1:
        try:
            solved_cond = _solve_single_condition(solved_cond)
        except Exception as F:
            raise Exception(f'Error Solving Condition: {str(F)}\n'
                            f'\tCondition: [{condition}]\n'
                            f'\tProgress:  [{" ".join(solved_cond)}]\n\n' +
                            qpcblock.get_formatted_info())
    
    return solved_cond[0]


def _solve_single_condition(cond):
    index = 1
    result = 0
    # highest precedence order
    if "<" in cond:
        index = cond.index("<")
        if int(cond[index - 1]) < int(cond[index + 1]):
            result = 1
    
    elif "<=" in cond:
        index = cond.index("<=")
        if int(cond[index - 1]) <= int(cond[index + 1]):
            result = 1
    
    elif ">=" in cond:
        index = cond.index(">=")
        if int(cond[index - 1]) >= int(cond[index + 1]):
            result = 1
    
    elif ">" in cond:
        index = cond.index(">")
        if int(cond[index - 1]) > int(cond[index + 1]):
            result = 1
    
    # next in order of precedence, check equality
    # you can compare stings with these 2
    elif "==" in cond:
        index = cond.index("==")
        if str(cond[index - 1]) == str(cond[index + 1]):
            result = 1
    
    elif "!=" in cond:
        index = cond.index("!=")
        if str(cond[index - 1]) != str(cond[index + 1]):
            result = 1
    
    # and then, check for any &&'s
    elif "&&" in cond:
        index = cond.index("&&")
        if int(cond[index - 1]) > 0 and int(cond[index + 1]) > 0:
            result = 1
    
    # and finally, check for any ||'s
    elif "||" in cond:
        index = cond.index("||")
        if int(cond[index - 1]) > 0 or int(cond[index + 1]) > 0:
            result = 1
    
    cond[index] = result
    del cond[index + 1]
    del cond[index - 1]
    
    return cond


def add_spacing_to_condition(cond):
    cond = cond.strip(" ")
    
    if ">=" not in cond:
        cond = cond.replace(">", " > ")
    if "<=" not in cond:
        cond = cond.replace("<", " < ")
    
    for operator in ("<=", ">=", "==", "||", "&&"):
        cond = cond.replace(operator, ' ' + operator + ' ')
    
    return cond


def read_file(path: str, keep_quotes: bool = False, allow_escapes: bool = True, multiline_quotes: bool = True) -> QPCBlockBase:
    path = posix_path(path)
    lexer = QPCLexer(path, keep_quotes, allow_escapes, multiline_quotes)
    qpc_file = QPCBlockBase(path)
    path = posix_path(os.getcwd() + "/" + path)
    parse_recursive(lexer, qpc_file, path)
    return qpc_file


def parse_recursive(lexer, block, path):
    while lexer.char_num < lexer.file_len - 1:
        key, line_num = lexer.next_key()
        
        if not key:
            if lexer.next_symbol() == "}" or lexer.char_num == lexer.file_len:
                return
            print("empty key? might work, who knows")
            block.print_info()
        
        # line_num = lexer.line_num
        values = lexer.next_value_list()
        condition = lexer.next_condition()
        
        sub_block = block.add_item(key, values, condition, line_num)
        
        next_symbol = lexer.next_symbol()
        if next_symbol == "{":
            parse_recursive(lexer, sub_block, path)
        elif next_symbol == "}":
            return


class QPCLexer:
    def __init__(self, path: str, keep_quotes: bool = False, allow_escapes: bool = True, multiline_quotes: bool = True):
        self.char_num = 0
        self.line_num = 1
        self.path = path
        self.keep_quotes = keep_quotes
        self.allow_escapes = allow_escapes
        self.multiline_quotes = multiline_quotes
        
        try:
            with open(path, mode="r", encoding="utf-8") as file:
                self.file = file.read()
        except UnicodeDecodeError:
            with open(path, mode="r", encoding="ansi") as file:
                self.file = file.read()
            
        self.file_len = len(self.file) - 1
        
        self.chars_escape = {'\'', '"', '\\'}
        self.chars_comment = {'/', '*'}
        self.chars_item = {'{', '}'}
        self.chars_cond = {'[', ']'}
        self.chars_space = {' ', '\t'}
        self.chars_quote = {'"', '\''}
    
    def next_value_list(self):
        values = []
        current_value = ''
        while self.char_num < self.file_len:
            char = self.file[self.char_num]
            
            if char in self.chars_item:
                break
            
            if char in self.chars_space:
                if current_value:
                    if current_value != '\\':
                        values.append(current_value)
                        current_value = ''
                self.char_num += 1
                continue
            
            if char in {'"', '\''}:
                values.append(self.read_quote(char))
                current_value = ""
                continue
            
            # skip escape
            if char == '\\' and self.next_char() in self.chars_escape:
                self.char_num += 2
                current_value += self.file[self.char_num]
                # char = self.file[self.char_num]
            
            elif char == '\n':
                # self.line_num += 1
                if not current_value.endswith("\\"):
                    if current_value and not current_value.startswith('[') and not current_value.endswith(']'):
                        values.append(current_value)
                    # self.char_num += 1
                    break
                else:
                    self.line_num += 1
            
            elif char == '/' and self.next_char() in self.chars_comment:
                self.skip_comment()
                self.char_num -= 1  # shut
            
            else:
                if self.file[self.char_num] in self.chars_cond:
                    break
                if current_value == '\\':
                    current_value = ''
                current_value += self.file[self.char_num]
            
            self.char_num += 1
        
        return values
    
    def next_char(self):
        if self.char_num + 1 >= self.file_len:
            return None
        return self.file[self.char_num + 1]
    
    # used to be NextString, but i only used it for keys
    def next_key(self):
        string = ""
        line_num = 0
        skip_list = {' ', '\t', '\n'}
        
        while self.char_num < self.file_len:
            char = self.file[self.char_num]
            
            if char in self.chars_item:
                line_num = self.line_num
                break
            
            elif char in self.chars_space:
                if string:
                    line_num = self.line_num
                    break
            
            elif char in self.chars_quote:
                string = self.read_quote(char)
                line_num = self.line_num
                break
            
            # skip escape
            elif char == '\\' and self.next_char() in self.chars_escape:
                self.char_num += 2
                string += self.file[self.char_num]
                # char = self.file[self.char_num]
            
            elif char in skip_list:
                if string:
                    # self.char_num += 1
                    line_num = self.line_num
                    # if char == '\n':
                    #     self.line_num += 1
                    break
                if char == '\n':
                    self.line_num += 1
            
            elif char == '/' and self.next_char() in self.chars_comment:
                self.skip_comment()
            
            else:
                string += self.file[self.char_num]
            
            self.char_num += 1
        
        return string, line_num
    
    def next_symbol(self):
        while self.char_num < self.file_len:
            char = self.file[self.char_num]
            
            if char in self.chars_item:
                self.char_num += 1
                return char
            
            # skip escape
            elif char == '\\' and self.next_char() in self.chars_escape:
                self.char_num += 2
            
            elif char == '/' and self.next_char() in self.chars_comment:
                self.skip_comment()
            
            elif char == '\n':
                self.line_num += 1
            
            elif char not in self.chars_space:
                break
            
            self.char_num += 1
        
        return None
    
    def next_condition(self):
        condition = ''
        while self.char_num < self.file_len:
            char = self.file[self.char_num]
            
            if char in self.chars_item:
                break
            
            elif char == '[':
                self.char_num += 1
                continue
            
            elif char == ']':
                self.char_num += 1
                break
            
            elif char in self.chars_space:
                self.char_num += 1
                continue
            
            elif char == '\n':
                self.line_num += 1
                self.char_num += 1
                break
            
            elif char == '/' and self.next_char() in self.chars_comment:
                self.skip_comment()
            
            else:
                condition += self.file[self.char_num]
            
            self.char_num += 1
        
        return condition
    
    def skip_comment(self):
        self.char_num += 1
        char = self.file[self.char_num]
        if char == '/':
            # keep going until \n
            while True:
                self.char_num += 1
                if self.file[self.char_num] == "\n":
                    self.line_num += 1
                    break
        
        elif char == '*':
            while True:
                char = self.file[self.char_num]
                
                if char == '*' and self.next_char() == '/':
                    self.char_num += 1
                    break
                
                if char == "\n":
                    self.line_num += 1
                
                self.char_num += 1
    
    def read_quote(self, quote_char):
        if self.keep_quotes:
            quote = quote_char
        else:
            quote = ''
        
        while self.char_num < self.file_len:
            self.char_num += 1
            char = self.file[self.char_num]
            
            if char == '\\' and self.next_char() in self.chars_escape and self.allow_escapes:
                quote += self.next_char()
                self.char_num += 1
            elif char == quote_char:
                if self.keep_quotes:
                    quote += char
                break
            elif char == "\n" and not self.multiline_quotes:
                break
            else:
                quote += char
        
        self.char_num += 1
        return quote
