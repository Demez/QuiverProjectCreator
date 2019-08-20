# Reads QPC files and returns a list of QPCBlocks

import os
from qpc_base import args


class QPCBlock:
    def __init__(self, file_path, line_num, key, values, condition):
        self.key = key
        self.values = values
        self.condition = condition
        self.items = []
        self.line_num = line_num
        self.file_path = file_path
    
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
        
        
def ReadFile(path):
    lexer = QPCLexer(path)
    qpc_file = []
    path = os.getcwd() + os.sep + path

    while lexer.chari < lexer.file_len:
        key, line_num = lexer.NextKey()
        
        if not key:
            break  # end of file
        
        values = lexer.NextValueList()
        condition = lexer.NextCondition()
        
        block = QPCBlock(path, line_num, key, values, condition)
        
        if lexer.NextSymbol() == "{":
            CreateSubBlock(lexer, block, path)
            pass
        
        qpc_file.append(block)
    
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

        sub_block = QPCBlock(path, line_num, key, values, condition)

        block.items.append(sub_block)
    
        next_symbol = lexer.NextSymbol()
        if next_symbol == "{":
            CreateSubBlock(lexer, sub_block, path)
        elif next_symbol == "}":
            return
        
    
class QPCLexer:
    def __init__(self, path):
        self.chari = 0
        self.linei = 1
        self.path = path
        
        with open(path, mode="r", encoding="utf-8") as file:
            self.file = file.read()
        self.file_len = len(self.file) - 1
        
        # maybe using this would be faster?
        self.keep_from = 0
        
        self.escape_chars = {'\'', '"', '\\'}
        self.comment_chars = {'/', '*'}
        
    def NextValueList(self):
        values = []
        current_value = ''
        while self.chari < self.file_len:
            char = self.file[self.chari]

            if char in {'{', '}'}:
                break
                
            if char in {' ', '\t'}:
                if current_value:
                    if current_value != '\\':
                        values.append(current_value)
                        current_value = ''
                self.chari += 1
                continue
    
            if char in {'"', '\''}:
                values.append(self.ReadQuote(char))
                continue
    
            # skip escape
            if char == '\\' and self.NextChar() in self.escape_chars:
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

            elif char == '/' and self.NextChar() in self.comment_chars:
                self.SkipComment()
    
            else:
                if self.file[self.chari] in {'[', ']'}:
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
            
            if char in {'{', '}'}:
                line_num = self.linei
                break

            elif char in {' ', '\t'}:
                if string:
                    line_num = self.linei
                    break

            elif char in {'"', '\''}:
                string = self.ReadQuote(char)
                line_num = self.linei
                break
            
            # skip escape
            elif char == '\\' and self.NextChar() in self.escape_chars:
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
                
            elif char == '/' and self.NextChar() in self.comment_chars:
                self.SkipComment()
                
            else:
                string += self.file[self.chari]

            self.chari += 1
            
        return string, line_num

    def NextSymbol(self):
        symbol_list = {'{', '}'}
        
        while self.chari < self.file_len:
            char = self.file[self.chari]

            if char in symbol_list:
                self.chari += 1
                return char
            
            # skip escape
            elif char == '\\' and self.NextChar() in self.escape_chars:
                self.chari += 2
            
            elif char == '/' and self.NextChar() in self.comment_chars:
                self.SkipComment()
                
            elif char == '\n':
                self.linei += 1
                
            elif char not in {' ', '\t'}:
                break

            self.chari += 1
            
        return None

    def NextCondition(self):
        condition = ''
        while self.chari < self.file_len:
            char = self.file[self.chari]
        
            if char in {'{', '}'}:
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
        
            elif char == '/' and self.NextChar() in self.comment_chars:
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
        quote = ''
    
        while self.chari < self.file_len:
            self.chari += 1
            char = self.file[self.chari]
        
            if char == '\\' and self.NextChar() in self.escape_chars:
                quote += self.NextChar()
                self.chari += 1
            elif char == qchar:
                break
            else:
                quote += char
    
        self.chari += 1
        return quote

