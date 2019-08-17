# Reads Scripts, putting them into objects made with the ProjectBlock class

import os
from qpc_base import args


class ProjectBlock:
    def __init__( self, file_path, line_num, key, values=None, condition=None ):
        self.key = key
        if values:
            self.values = values
        else:
            self.values = []
        self.condition = condition
        self.items = []

        self.line_num = str(line_num)

        # split this by the root_dir and the file_path
        self.file_path = ''.join( os.getcwd().split(args.root_dir) ) + os.sep + file_path

    def AddItem( self, item ):
        self.items.append( item )

    # would be cool if i could change the colors on this
    def FatalError(self, message):
        print( "FATAL ERROR: " + message )
        self.PrintInfo()
        quit()

    # should Error and FatalError be the same?
    def Error(self, message):
        print( "ERROR: " + message )
        self.PrintInfo()

    def Warning(self, message):
        if not args.hide_warnings:
            print( "WARNING: " + message )
            self.PrintInfo()

    def InvalidOption(self, *valid_option_list):
        if not args.hide_warnings:
            print( "WARNING: Invalid Option" )
            print( "\tValid Options:\n\t\t" + '\n\t\t'.join(valid_option_list) )
            self.PrintInfo()

    def PrintInfo( self ):
        print(  "\tFile Path: " + self.file_path +
                "\n\tLine: " + self.line_num +
                "\n\tKey: " + self.key )

        if self.values:
            # if there is only one value, write it on the same line
            if len(self.values) == 1:
                print("\tValues: " + self.values[0] )
            else:
                print("\tValues:\n\t\t" + '\n\t\t'.join(self.values) )


def ReadFile( path ):
    try:
        with open( path, mode="r", encoding="utf-8" ) as file:
            file = file.read().splitlines()
        file = ParseFileByEachChar(file)
        file = FormatParsedFile( file )
        file = CreateFileBlockObjects( file, path )
        return file
    except FileNotFoundError:
        return None
    

# this is the slowest function, but it's not that bad now
def ParseFileByEachChar( config ):
    escape_chars = {'\'', '"'}
    comment_chars = {'/', '*'}
    
    def next_char():
        if chari >= len(line) - 1:
            return None
        return line[chari + 1]
    
    new_config = {}
    new_line = []
    # new_line_num = 0
    linei = 0
    while linei < len(config):
        line = config[linei].replace("\t", " ").strip()
        
        new_str = []
        keep_from = 0
        
        chari = 0
        while chari < len(line):
            char = line[chari]
            
            # split new_str on spaces
            if char == ' ':
                '''
                if new_str and new_str[0] != ' ':
                    if new_line and new_line[-1] == '\\':
                        del new_line[-1]
                        new_line.append(''.join(new_str))
                    else:
                        new_line.append(''.join(new_str))
                '''
                if new_str:
                    new_line.append(''.join(new_str))
                    new_str = []
                
            # skip escape
            if char == '\\' and next_char() in escape_chars:
                chari += 2
            
            elif char == '"' or char == '\'':
                qchar = char
                
                new_str += line[keep_from:chari]
                while chari < len(line) - 1:
                    chari += 1
                    char = line[chari]
                    
                    if char == '\\' and next_char() in escape_chars:
                        new_str += next_char()
                        chari += 1
                    elif char == qchar:
                        break
                    else:
                        new_str += char

                keep_from = chari + 1
            
            # breaks if a block starts with this and isn't a comment
            elif char == '/' and next_char() in comment_chars:
                chari += 1
                
                char = line[chari]
                if char == '/':
                    break
                
                elif char == '*':
                    chari = 0
                    in_comment = True
                    while in_comment:
                        linei += 1
                        line = config[linei]
                        
                        if not line:
                            continue
                            
                        for chari, char in enumerate(line):
                            if char == '*' and next_char() == '/':
                                new_str += line[chari + 2:]
                                keep_from = chari + 2
                                in_comment = False
                                break
                        
                        chari += 1
            
            elif char == '[':
                new_str += line[keep_from:chari]
                keep_from = chari
                while True:
                    chari += 1
                    char = line[chari]
                    
                    if char == '\\' and next_char() in escape_chars:
                        chari += 2
                    elif char == ']':
                        # don't want spaces
                        new_str += line[keep_from:chari + 1].replace(" ", '')
                        keep_from = chari + 1
                        break
            
            else:
                # split new_str on spaces
                if char != ' ':
                    new_str += char
                keep_from = chari + 1
            chari += 1
            
        if new_str:
            '''
            if new_line and new_line[-1] == '\\' and new_str[-1] != '\\':
                del new_line[-1]
                new_line.append(''.join(new_str))
            else:
            '''
            new_line.append(''.join(new_str))
            # if not new_line[-1] == '\\' or new_line_num == 0:
            #     new_line_num = linei + 1
            
        if new_line:
            # if not new_line[-1] == '\\':
            new_config[linei + 1] = new_line
            new_line = []
            # new_line_num = linei
        
        linei += 1
    
    return new_config


# Re-Formats the config, so no more blocks in one single line
def FormatParsedFile(script):
    new_config = {}
    last_item = []
    # for line_num, split_line in enumerate(script):
    for line_num, split_line in script.items():
        '''
        if "{" in split_line or "}" in split_line:
            new_split_line = []
            for item in split_line:

                if "{" in item or "}" in item:
                    # what about if the length is over 2?
                    if new_split_line:
                        new_config[line_num] = new_split_line
                    # TODO: this would override the existing line if the semicolon was put on the same line
                    new_config[line_num] = [item]
                    new_split_line = []

                elif len(new_split_line) >= 2:
                    new_config[line_num] = new_split_line
                    new_split_line = [item]

                else:
                    new_split_line.append( item )

        # aaaaaa
        '''
        if len(last_item) > 1 and last_item[-1] == "\\":
            if split_line:
                del list(new_config.values())[-1][-1]
                list(new_config.values())[-1].extend( split_line )
            continue

        else:
            new_config[line_num] = split_line
            last_item = split_line

    return new_config


# Purpose: to clean up the project script to make parsing it easier
def CreateFileBlockObjects( file, path ):
    cleaned_file = []
    line_num = 0

    line_nums = list(file.keys())
    lines = list(file.values())
    
    while line_num < len( file ):

        line_num, block = GetBlock(line_nums, lines, line_num)

        line_num = line_num - 1
        block = CreateFileBlockObject( block, path )
        cleaned_file.append( block )
            
        line_num += 1
        continue

    return cleaned_file


# this is also a bit slow
def CreateFileBlockObject( block, path ):
    condition = None
    block_lines = list(block.keys())
    block_values = list(block.values())

    block_0 = block_values[0]
    value_start = 1
    value_end = value_start + len(block_0[value_start:])
    
    if "[" in block_0[-1] and "]" in block_0[-1]:
        condition = block_0[-1][1:-1]  # no brackets on the ends
        value_end -= 1
        
    value_list = block_0[value_start:value_end]

    key = ProjectBlock( path, block_lines[0], block_0[0], value_list, condition )

    if len( block ) > 1:

        block_line_num = 1
        while block_line_num < len( block ):
            
            if block_values[block_line_num][0] != '{' and block_values[block_line_num][0] != '}':
                line_num, sub_block = GetBlock(block_lines, block_values, block_line_num)

                if isinstance( sub_block, dict ):
                    block_line_num = line_num  # - 1
                    sub_block = CreateFileBlockObject( sub_block, path )
                    key.AddItem( sub_block )
                    continue

            block_line_num += 1
            
    return key


# Returns a block into a list with each string split up starting from a line number
# def GetBlock( file, line_number ):
def GetBlock( line_nums, lines, line_number ):
    block_depth_num = 0
    
    block = { line_nums[line_number]: lines[line_number] }
    if lines[line_number] == ['{']:
        block_depth_num = 1

    line_number += 1
    
    # line_nums = list(file.keys())
    # lines = list(file.values())

    # for current_line_num, current_line in file.items():
    while line_number < len( lines ):

        current_line_num = line_nums[line_number]
        current_line = lines[line_number]
        
        # the value is split across multiple lines
    
        # last_line = list(file.values())[-1]
    
        # why?
        # if len(list(file.values())[-1]) > 1:
        #     if block_depth_num == 0 and current_line == []:
        #         break

        if ( current_line == ['{'] ) or ( block_depth_num != 0 ):
            block[current_line_num] = current_line

        # elif len(list(file.values())[-1]) > 1:
        #     if block_depth_num == 0:
        #         # this is a single line block like $Macro
        #         break

        else:
            break

        if current_line == ["{"]:
            block_depth_num += 1

        if current_line == ["}"]:
            block_depth_num -= 1

        line_number += 1

    return line_number, block

