# Reads Scripts, putting them into objects made with the ProjectBlock class

# TODO: figure out what is $CRCCHECK is
# may need to add a /checkfiles launch option to have this check if a file exists or not
# it would probably slow it down as well

import os
import hashlib
import qpc_base as base


# TODO: add file path for error reporting
class ProjectBlock:
    # def __init__( self, line_num, file_path, key, values=None, condition=None ):
    def __init__( self, line_num, key, values=None, condition=None ):
        self.key = key
        if values:
            self.values = values
        else:
            self.values = []
        self.condition = condition
        self.items = []

        self.line_num = str(line_num)
        # self.file_path = file_path

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
        print( "WARNING: " + message )
        self.PrintInfo()

    # def InvalidOption(self, valid_option_list):
    def InvalidOption(self, *valid_option_list):
        print( "Error: Invalid Option" )
        print( "\tValid Options:\n\t\t" + '\n\t\t'.join(valid_option_list) )
        self.PrintInfo()

    def PrintInfo( self ):
        print(  "\tLine: " + self.line_num +
                "\n\tKey: " + self.key )

        if self.values:
            # TODO: maybe if there is only one value, write it on the same line?
            if len(self.values) == 1:
                print("\tValues: " + self.values[0] )
            else:
                print("\tValues:\n\t\t" + '\n\t\t'.join(self.values) )

        # not really useful
        # if self.condition:
        #     print("\tCondition: " + self.condition)


# maybe add a depth variable here as well? idk
def ReadFile( path ):
    with open( path, mode="r", encoding="utf-8" ) as file:
        file = file.read().splitlines()
    file = RemoveCommentsAndFixLines( file, path )
    file = _FormatConfigBlocks( file )
    file = CreateFileBlockObjects( file )

    return file


def RemoveCommentsAndFixLines( config, file_path ):
    in_comment = False
    in_quote = False
    new_config = {}

    for line_num, line in enumerate(config):
        # TODO: check for quotes before removing comments,
        # we don't want to remove comments that are in quotes
        # removes all multi-line comments from the line
        # line = re.sub(r'/\*.*?\*/', r'', line)

        new_line = ''
        for char_num, char in enumerate(line):

            if not in_comment:
                if char == '"' and not line[char_num-1] == "\\":
                    in_quote = not in_quote

                if not in_quote and char_num+1 < len(line):
                    if char == "/" and line[char_num+1] == "/":
                        break

                    if char == "/" and line[char_num+1] == "*":
                        in_comment = True
                        char = ''

                if char == "\t":
                    char = ' '

                new_line += char

            elif line[char_num-1] == "*" and char == "/":
                in_comment = False

        # make sure we don't stay "in a quote" on the next line
        if in_quote:
            in_quote = False

            # TODO: might be able to move this into a function in base, idk

            # remove the last quote
            new_line_quote_split = new_line.rsplit( '"', 1 )
            quote_position_line = "{0}{1}".format(" " * len(new_line_quote_split[0]), "^")

            # TODO: use argparse
            if not base.FindCommand( "/hidewarnings" ):
                # might be an escape quote
                if new_line_quote_split[0][-1] == "\\":
                    print( "WARNING: tried to close quote with an escape character:" )
                else:
                    print( "WARNING: quote does not close, removing last quote:" )

                # report warning
                print(  "\tFile Path: " + file_path +
                        "\n\tLine: " + new_line +
                        "\n\t      " + quote_position_line +
                        "\n\tLine Number: " + str(line_num+1) )

            # might be an escape quote
            if new_line_quote_split[0][-1] == "\\":
                print("WARNING: tried to close quote with an escape character:")
                # just add another quote onto it to close it
                new_line = '""'.join(new_line_quote_split)
            else:
                print("WARNING: quote does not close, removing last quote:")
                new_line = ''.join(new_line_quote_split)

        new_line = _RemoveQuotesAndSplitLine(new_line)

        if new_line:
            new_line = JoinConditionLine(new_line)
            new_config[line_num+1] = new_line

    return new_config


# remove quotes in the string if there is any
def _RemoveQuotesAndSplitLine( line ):

    # add a gap in between these if they exist just in case
    # so we can have no spaces in the actual file if we want
    # line = line.replace( "{", " { ")
    # line = line.replace( "}", " } ")

    line_split = []
    raw_line_split = line.split(" ")

    str_num = 0
    while str_num < len( raw_line_split ):
        string = raw_line_split[ str_num ]

        if string.startswith( '"' ) or '\\"' in string:

            if string.endswith( '"' ):
                str_len = len( string )
                string = string[ 1: str_len-1 ]

            else:
                quote = string[1:]  # strip the start quote off
                quote_str_num = str_num + 1

                # this will keep adding strings together until one of them ends with a quote
                while quote_str_num < len(raw_line_split) and ( quote.endswith('\\"') or not quote.endswith('"') ):
                    quote += " " + raw_line_split[ quote_str_num ]
                    quote_str_num += 1

                if '\\"' in quote:
                    # replace '\\"' with '"'
                    quote = '"'.join(quote.split('\\"'))

                str_num = quote_str_num - 1
                string = quote[:-1]  # strip the end quote off

        elif not string:
            str_num += 1
            continue

        line_split.append(string)
        str_num += 1

    return line_split


def JoinConditionLine(line_split):

    cond_line_len, cond_line = GetConditionLine(line_split)

    new_line_split = line_split
    # get rid of the conditional from the line
    if cond_line:
        for string in line_split:
            if "[" in string:
                # line_split = line_split[ :line_split.index(string) ]
                index = line_split.index(string)
                new_line_split = line_split[ :index ]
                new_line_split.append( cond_line )
                new_line_split.extend( line_split[ index+cond_line_len: ] )
                break

    return new_line_split


def GetConditionLine(line_split):

    found_cond = False
    cond_len = 0

    for string_num, string in enumerate(line_split):
        if "[" in string:
            if cond_len == 0:
                found_cond = line_split[ string_num ]

        if found_cond:
            cond_len += 1
            if "]" in string:
                break

    if found_cond != False:
        line = ''.join(line_split)
        cond_line = "[" + ( line.split( "[" )[1] ).split( "]" )[0] + "]"
        return cond_len, cond_line

    return 0, None


# Re-Formats the config, so no more blocks in one single line
def _FormatConfigBlocks(script):

    new_config = {}
    # for line_num, split_line in enumerate(script):
    for line_num, split_line in script.items():
        if "{" in split_line or "}" in split_line:
            new_split_line = []
            for item in split_line:

                if "{" in item or "}" in item:
                    # what about if the length is over 2?
                    if new_split_line:
                        # new_config.append( new_split_line )
                        new_config[line_num] = new_split_line
                    # TODO: this would override the existing line if the semicolon was put on the same line
                    new_config[line_num] = [item]
                    new_split_line = []

                elif len(new_split_line) >= 2:
                    # new_config.append( new_split_line )
                    new_config[line_num] = new_split_line
                    new_split_line = [item]

                else:
                    new_split_line.append( item )

            # new_config.append( new_split_line )

        elif len(new_config) > 1 and len(list(new_config.values())[-1]) > 1 and list(new_config.values())[-1][-1] == "\\":
            if split_line:
                del list(new_config.values())[-1][-1]
                list(new_config.values())[-1].extend( split_line )
            continue

        else:
            # new_config.append( split_line )

            new_config[line_num] = split_line

    return new_config


# Purpose: to clean up the project script to make parsing it easier
def CreateFileBlockObjects( file ):

    cleaned_file = []

    line_num = 0
    while line_num < len( file ):

        line_num, block = GetFileBlockSplit( file, line_num )

        line_num = line_num - 1
        block = CreateFileBlockObject( block )
        cleaned_file.append( block )
            
        line_num += 1
        continue

    return cleaned_file


def CreateFileBlockObject( block ):

    value_list = []
    condition = None

    block_0 = list(block.values())[0]
    value_index = 1
    while len(list(block.values())[0]) > value_index:
        # don't add any conditional to the value_list
        if "[" in block_0[value_index] or "]" in block_0[value_index]:
            condition = block_0[value_index][1:-1]  # no brackets on the ends
        else:
            value_list.append( block_0[value_index] )
        value_index += 1

    # key = ProjectBlock( block_0[0], value_list, condition )
    key = ProjectBlock( list(block.keys())[0], block_0[0], value_list, condition )

    if len( block ) > 1:

        block_values = list(block.values())

        block_line_num = 1
        while block_line_num < len( block ):

            if block_values[block_line_num] != [] and block_values[block_line_num][0] != '{' and \
                    block_values[block_line_num][0] != '}':

                line_num, sub_block = GetFileBlockSplit( block, block_line_num )

                if isinstance( sub_block, dict ):
                    block_line_num = line_num  # - 1
                    sub_block = CreateFileBlockObject( sub_block )
                    key.AddItem( sub_block )
                    continue

            block_line_num += 1

    return key


# Returns a block into a list with each string split up starting from a line number
def GetFileBlockSplit( file, line_number ):

    block_depth_num = 0

    block = { list(file.keys())[line_number]: list(file.values())[line_number] }
    if list(file.values())[line_number] == ['{']:
        block_depth_num = 1
    # else:
    # if file[ line_number ] != ["{"]:
    #     return [ line_number, block ]

    line_number += 1

    while line_number < len( file ):

        current_line_num = list(file.keys())[line_number]
        current_line = list(file.values())[line_number]
        
        # the value is split across multiple lines
        if len(list(file.values())[-1]) > 1:
            if block_depth_num == 0 and current_line == []:
                break

        if current_line != []:
            if ( current_line == ['{'] ) or ( block_depth_num != 0 ):
                block[current_line_num] = current_line

            elif len(list(file.values())[-1]) > 1:
                if block_depth_num == 0:
                    # this is a single line block like $Macro
                    break

            else:
                break

        if current_line == ["{"]:
            block_depth_num += 1

        if current_line == ["}"]:
            block_depth_num -= 1

        line_number += 1

    return line_number, block

