# Reads QPC files and returns a list of QPCBlocks

import os
from pathlib import Path
from re import compile
from qpc_base import args, FixPathSeparator


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

    def ToString(self, depth=0, quote_keys=False, quote_values=False, break_multi_value=False, break_on_key=False):
        final_string = ""
        for item in self.items:
            final_string += item.ToString(depth, quote_keys) + "\n"
        return final_string
        
    def AddItem(self, key: str, values: list, condition: str = "", line_num: int = 0):
        sub_qpc = QPCBlock(self, key, values, condition, file_path=self.file_path, line_num=line_num)
        self.items.append(sub_qpc)
        return sub_qpc
        
    def AddItemAtIndex(self, index: int, key: str, values: list, condition: str = "", line_num: int = 0):
        sub_qpc = QPCBlock(self, key, values, condition, file_path=self.file_path, line_num=line_num)
        self.items.insert(index, sub_qpc)
        return sub_qpc

    def GetItem(self, item_key):
        for item in self.items:
            if item.key == item_key:
                return item
        return None

    def GetItemValues(self, item_key):
        for item in self.items:
            if item.key == item_key:
                return item.values
        return None

    def GetAllItems(self, item_key):
        items = []
        for item in self.items:
            if item.key == item_key:
                items.append(item)
        return items

    # TODO: shorten these 4 function names?
    def GetItemsThatPassCondition(self, macros: list):
        items = []
        for item in self.items:
            if SolveCondition(item.condition, macros):
                items.append(item)
        return items
    
    def GetItemKeysThatPassCondition(self, macros: list):
        items = []
        for item in self.items:
            if SolveCondition(item.condition, macros):
                items.append(item.key)
        return items
    
    def GetItemValuesThatPassCondition(self, macros: list):
        items = []
        for item in self.items:
            if SolveCondition(item.condition, macros):
                items.extend(item.values)
        return items
    
    # way too long
    def GetItemKeyAndValuesThatPassCondition(self, macros: list):
        items = []
        for item in self.items:
            if SolveCondition(item.condition, macros):
                items.extend([item.key, *item.values])
        return items

    # probably useless
    def GetValuesOfAllItems(self, item_key):
        items = []
        for item in self.items:
            if item.key == item_key:
                items.append(item)
        return items
    
    def GetAllKeysInItems(self):
        keys = []
        [keys.append(value.key) for value in self.items]
        return keys
    
    def GetIndexOfItem(self, qpc_item):
        try:
            return self.items.index(qpc_item)
        except IndexError:
            return None


class QPCBlock(QPCBlockBase):
    def __init__(self, parent, key, values, condition: str = "", file_path: str = "", line_num: int = 0):
        super().__init__(file_path)
        self.parent = parent
        self.key = key
        self.values = values
        self.condition = condition
        self.line_num = line_num

    def ToString(self, depth=0, quote_keys=False, quote_values=False, break_multi_value=False, break_on_key=False):
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
                    formatted_value = "{0}".format(value.replace("'", "\\'").replace('"', '\\"'))
                else:
                    formatted_value = "{0}".format(value.replace("'", "\\'"))
                    formatted_value = "{0}".format(
                        formatted_value[0] + formatted_value[1:-1].replace('"', '\\"') + formatted_value[-1])
                    
                if quote_values:
                    string += " \"{0}\"".format(formatted_value)
                else:
                    string += " {0}".format(formatted_value)
                # untested
                if break_multi_value and value_index < len(self.values):
                    string += " \\\n{0}{1}".format(indent, " " * key_indent)
    
        if self.condition:
            string += " [" + AddSpacingToCondition(self.condition) + "]"
    
        if self.items:
            if 0 < index < len(self.parent.items):
                if not self.parent.items[index - 1].items:
                    string = "\n" + string
                    
            string += "\n" + indent + "{\n"
            for item in self.items:
                string += item.ToString(depth+1, quote_keys) + "\n"
            string += indent + "}"
            
            if index < len(self.parent.items) - 1:
                string += "\n"
    
        return string

    def GetKeyValues(self):
        return [self.key, *self.values]

    def SolveCondition(self, macros: dict) -> int:
        return SolveCondition(self.condition, macros)

    def InvalidOption(self, *valid_option_list):
        if not args.hide_warnings:
            print( "WARNING: Invalid Option" )
            print( "\tValid Options:\n\t\t" + '\n\t\t'.join(valid_option_list) )
            self.PrintInfo()
    
    # would be cool if i could change the colors on this
    def FatalError(self, message):
        print("FATAL ERROR: " + message)
        self.PrintInfo()
        quit()
    
    # should Error and FatalError be the same?
    def Error(self, message):
        print("ERROR: " + message)
        self.PrintInfo()
    
    def Warning(self, message):
        if not args.hide_warnings:
            print("WARNING: " + message)
            self.PrintInfo()
    
    def PrintInfo(self):
        # TODO: this path is relative to the current directory
        print("\tFile Path: " + self.file_path +
              "\n\tLine: " + str(self.line_num) +
              "\n\tKey: " + self.key)

        if self.values:
            # if there is only one value, write it on the same line
            if len(self.values) == 1:
                print("\tValues: " + self.values[0])
            else:
                print("\tValues:\n\t\t" + '\n\t\t'.join(self.values))
                
            
# maybe make a comment object so when you re-write the file, you don't lose comments
class Comment:
    def __init__(self):
        pass


def ReplaceMacrosCondition(split_string, macros):
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


def SolveCondition(condition, macros):
    if not condition:
        return True
    
    # solve any sub conditionals first
    while "(" in condition:
        sub_cond_line = (condition.split('(')[1]).split(')')[0]
        sub_cond_value = SolveCondition(sub_cond_line, macros)
        condition = condition.split('(', 1)[0] + str(sub_cond_value * 1) + condition.split(')', 1)[1]
    
    split_string = COND_OPERATORS.split(condition)
    
    condition = ReplaceMacrosCondition(split_string, macros)
    
    if len(condition) == 1:
        try:
            return int(condition[0])
        except ValueError:
            return 1
    
    while len(condition) > 1:
        condition = SolveSingleCondition(condition)
    
    return condition[0]


def SolveSingleCondition(cond):
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


def AddSpacingToCondition(cond):
    cond = cond.strip(" ")
    
    if ">=" not in cond:
        cond = cond.replace(">", " > ")
    if "<=" not in cond:
        cond = cond.replace("<", " < ")
    
    for operator in ("<=", ">=", "==", "||", "&&"):
        cond = cond.replace(operator, ' ' + operator + ' ')
    
    return cond
    
        
def ReadFile(path, keep_quotes=False):
    path = FixPathSeparator(path)
    lexer = QPCLexer(path, keep_quotes)
    qpc_file = QPCBlockBase(path)
    path = os.getcwd() + os.sep + path

    while lexer.chari < lexer.file_len:
        key, line_num = lexer.NextKey()
        
        if not key:
            break  # end of file
        
        values = lexer.NextValueList()
        condition = lexer.NextCondition()

        block = qpc_file.AddItem(key, values, condition, line_num)
        
        if lexer.NextSymbol() == "{":
            CreateSubBlock(lexer, block, path)
            pass
    
    return qpc_file


def CreateSubBlock(lexer, block, path):
    while lexer.chari < lexer.file_len - 1:
        key, line_num = lexer.NextKey()
        
        if not key:
            if lexer.NextSymbol() == "}":
                return
            print( "uhhhhhhh" )
        
        # line_num = lexer.linei
        values = lexer.NextValueList()
        condition = lexer.NextCondition()

        sub_block = block.AddItem(key, values, condition, line_num)
    
        next_symbol = lexer.NextSymbol()
        if next_symbol == "{":
            CreateSubBlock(lexer, sub_block, path)
        elif next_symbol == "}":
            return
        
    
class QPCLexer:
    def __init__(self, path, keep_quotes=False):
        self.chari = 0
        self.linei = 1
        self.path = path
        self.keep_quotes = keep_quotes

        with open(path, mode="r", encoding="utf-8") as file:
            self.file = file.read()
        self.file_len = len(self.file) - 1
        
        self.chars_escape = {'\'', '"', '\\'}
        self.chars_comment = {'/', '*'}
        self.chars_item = {'{', '}'}
        self.chars_cond = {'[', ']'}
        self.chars_space = {' ', '\t'}
        self.chars_quote = {'"', '\''}
        
    def NextValueList(self):
        values = []
        current_value = ''
        while self.chari < self.file_len:
            char = self.file[self.chari]

            if char in self.chars_item:
                break
                
            if char in self.chars_space:
                if current_value:
                    if current_value != '\\':
                        values.append(current_value)
                        current_value = ''
                self.chari += 1
                continue
    
            if char in {'"', '\''}:
                values.append(self.ReadQuote(char))
                current_value = ""
                continue
    
            # skip escape
            if char == '\\' and self.NextChar() in self.chars_escape:
                self.chari += 2
                current_value += self.file[self.chari]
                # char = self.file[self.chari]
    
            elif char == '\n':
                # self.linei += 1
                if not current_value.endswith("\\"):
                    if current_value and not current_value.startswith('[') and not current_value.endswith(']'):
                        values.append(current_value)
                    # self.chari += 1
                    break
                else:
                    self.linei += 1

            elif char == '/' and self.NextChar() in self.chars_comment:
                self.SkipComment()
                self.chari -= 1  # shut
    
            else:
                if self.file[self.chari] in self.chars_cond:
                    break
                if current_value == '\\':
                    current_value = ''
                current_value += self.file[self.chari]
    
            self.chari += 1
        
        return values

    def NextChar(self):
        if self.chari + 1 >= self.file_len:
            return None
        return self.file[self.chari + 1]

    # used to be NextString, but i only used it for keys
    def NextKey(self):
        string = ''
        line_num = 0
        skip_list = {' ', '\t', '\n'}
        
        while self.chari < self.file_len:
            char = self.file[self.chari]
            
            if char in self.chars_item:
                line_num = self.linei
                break

            elif char in self.chars_space:
                if string:
                    line_num = self.linei
                    break

            elif char in self.chars_quote:
                string = self.ReadQuote(char)
                line_num = self.linei
                break
            
            # skip escape
            elif char == '\\' and self.NextChar() in self.chars_escape:
                self.chari += 2
                string += self.file[self.chari]
                # char = self.file[self.chari]
            
            elif char in skip_list:
                if string:
                    # self.chari += 1
                    line_num = self.linei
                    # if char == '\n':
                    #     self.linei += 1
                    break
                if char == '\n':
                    self.linei += 1
                
            elif char == '/' and self.NextChar() in self.chars_comment:
                self.SkipComment()
                
            else:
                string += self.file[self.chari]

            self.chari += 1
            
        return string, line_num

    def NextSymbol(self):
        while self.chari < self.file_len:
            char = self.file[self.chari]

            if char in self.chars_item:
                self.chari += 1
                return char
            
            # skip escape
            elif char == '\\' and self.NextChar() in self.chars_escape:
                self.chari += 2
            
            elif char == '/' and self.NextChar() in self.chars_comment:
                self.SkipComment()
                
            elif char == '\n':
                self.linei += 1
                
            elif char not in self.chars_space:
                break

            self.chari += 1
            
        return None

    def NextCondition(self):
        condition = ''
        while self.chari < self.file_len:
            char = self.file[self.chari]
        
            if char in self.chars_item:
                break
        
            elif char == '[':
                self.chari += 1
                continue
        
            elif char == ']':
                self.chari += 1
                break
        
            elif char in {' ', '\t'}:
                self.chari += 1
                continue
        
            elif char == '\n':
                self.linei += 1
                self.chari += 1
                break
        
            elif char == '/' and self.NextChar() in self.chars_comment:
                self.SkipComment()
        
            else:
                condition += self.file[self.chari]
        
            self.chari += 1
            
        return condition
    
    def SkipComment(self):
        self.chari += 1
        char = self.file[self.chari]
        if char == '/':
            # keep going until \n
            while True:
                self.chari += 1
                if self.file[self.chari] == "\n":
                    self.linei += 1
                    break
    
        elif char == '*':
            while True:
                char = self.file[self.chari]
            
                if char == '*' and self.NextChar() == '/':
                    self.chari += 1
                    break
            
                if char == "\n":
                    self.linei += 1
            
                self.chari += 1

    def ReadQuote(self, qchar):
        if self.keep_quotes:
            quote = qchar
        else:
            quote = ''
    
        while self.chari < self.file_len:
            self.chari += 1
            char = self.file[self.chari]
        
            if char == '\\' and self.NextChar() in self.chars_escape:
                quote += self.NextChar()
                self.chari += 1
            elif char == qchar:
                if self.keep_quotes:
                    quote += char
                break
            else:
                quote += char
    
        self.chari += 1
        return quote

