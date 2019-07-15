
import sys
import re

def FindItemsWithStartingChar( search_list, item ):
    found_args = []
    index = 0

    for arg in search_list:
        if search_list[index].startswith( item ):
            arg_value = arg.split( item )[1]
            found_args.append( arg_value )
        index += 1

    if found_args:
        return found_args
    else:
        return None


def FindItem( list, item, return_value = False ):
    if item in list:
        if return_value:
            return list[ list.index( item ) ]
        else:
            return True
    else:
        return False


def FindItemValue( list, item, return_value = False ):
    if item in list:
        if return_value:
            return list[ list.index( item ) + 1 ]
        else:
            return True
    else:
        return False


def FindCommand( arg, return_value = False ):
    return FindItemValue( sys.argv, arg, return_value )


def FindCommandValues( arg ):
    return FindItemsWithStartingChar( sys.argv, arg )


def CreateNewDictValue( dictionary, key, value_type ):
    try:
        dictionary[ key ]
    except KeyError:
        if value_type == "dict":
            dictionary[ key ] = {}
        elif value_type == "list":
            dictionary[ key ] = []
        elif value_type == "str":
            dictionary[ key ] = ""


# TODO: replace this with enumerate()
def RemoveCommentsAndFixLines( config ):

    in_comment = False

    # split each string by "/" and check if the start and end characters in each item in the split string is "*"
    # and some other stuff
    line_num = 0
    while line_num < len( config ):
        config[ line_num ] = config[ line_num ].split( "//", 1 )[0] # comment type 1
        if config[ line_num ] == '':
            line_num += 1
            continue

        # removes all multiline comments from the line
        config[line_num] = re.sub( r'/\*.*?\*/', r'', config[line_num] )

        if in_comment:
            if "*/" in config[line_num]:
                config[ line_num ] = config[line_num].split( "*/", 1 )[1]
                # del line_split[1]
                # del line_split[1]
                in_comment = False
                continue # not incrementing the line number so i can run through this again
            else:
                config[line_num] = ''
                line_num += 1
                continue

        if "/*" in config[line_num]:
            config[ line_num ] = config[line_num].split( "/*", 1 )[0]
            in_comment = True

        if "\n" in config[line_num]:
            config[line_num] = ''.join( config[line_num].split( "\n" ) )

        # makes sure we don't have about 500 tabs in between strings
        if "\t" in config[ line_num ]:
            tab_space = config[line_num].split( "\t" )
            new_line = []
            for item in tab_space:
                if item != '':
                    new_line.append( item )

            config[line_num] = ' '.join( new_line )

        # makes sure we don't have about 500 spaces in between strings
        if ' ' in config[line_num]:
            spaces = config[line_num].split( " " )
            new_line = []
            for item in spaces:
                if item != '':
                    new_line.append( item )

            config[line_num] = ' '.join( new_line )

        line_num += 1

    return config


def SolveConditional( cond_line, conditionals ):
    
    if cond_line == None:
        return True

    sub_cond_values = []

    # split by "(" for any sub conditionals
    # maybe do the same for anything with "!" in it?
    if "(" in cond_line:
        sub_cond_line = ( cond_line.split( '(' )[1] ).split( ')' )[0]

        sub_cond_values.append( SolveConditional( sub_cond_line, conditionals ) )

        # convert the booleans to ints
        sub_cond_values = [boolean*1 for boolean in sub_cond_values]

        cond_line = ( cond_line.split( '(' ) )
        cond_line = cond_line[0] + cond_line[1].split( ')' )[1]

    operator_list = [ "||", "&&", ">=", "<=", "=", ">", "<" ]

    cond_list = []
    cond_test = []

    if not cond_list:
        for operator in operator_list:
            if operator in cond_line:
                cond_list.extend( cond_line.split( operator ) )

                if operator == "||" or operator == "&&":
                    cond_test.append( operator )
                else:
                    cond_test = operator
                    break
            
    if not cond_list:
        cond_list.append( cond_line )

    # are there any empty values here?
    if '' in cond_list:
        del cond_list[ cond_list.index('') ]

    for cond in cond_list:
        cond_index = cond_list.index( cond )
        if "$" in cond_list[ cond_index ]:
            if cond.startswith( "!" ):
                # set the last value to opposite of what it was

                if cond[1:] in conditionals: # and conditionals[ cond[1:] ] == 0:
                    cond_list[ cond_index ] = int( not conditionals[ cond[1:] ] )
                else:
                    cond_list[ cond_index ] = 1
            else:
                try:    cond_list[ cond_index ] = conditionals[ cond ]
                except: cond_list[ cond_index ] = 0
        else:
            try:
                cond_list[ cond_index ] = int( cond )
            except Exception as Error:
                print( repr( Error ) )

    [ cond_list.insert( 0, value ) for value in sub_cond_values ]

    if not cond_test:
        if not cond_list:
            return False  # ?
        elif sum( cond_list ) > 0:
            return True
        else:
            return False

    elif "||" in cond_test or "&&" in cond_test:
        for test in cond_test:

            if test == "||":
                # can't be below zero
                if sum( cond_list ) > 0:
                    return True

            elif test == "&&":
                # all of them have to be true, so we can't have any False
                if not 0 in cond_list:
                    return True
    else:
        if cond_test == ">":
            if cond_list[0] > cond_list[1]:
                return True

        elif cond_test == ">=":
            if cond_list[0] >= cond_list[1]:
                return True

        elif cond_test == "=":
            if cond_list[0] == cond_list[1]:
                return True

        elif cond_test == "<=":
            if cond_list[0] <= cond_list[1]:
                return True

        elif cond_test == "<":
            if cond_list[0] < cond_list[1]:
                return True

    return False


# remove quotes in the string if there is any
def RemoveQuotes( line_split ):

    if isinstance( line_split, str ):
        if line_split.startswith( '"' ):
            if line_split.endswith( '"' ):
                line_split = line_split[ 1 : -1 ]
    else:
        str_index = 0
        while str_index < len( line_split ):

            if line_split[ str_index ].startswith( '"' ) or '\\"' in line_split[ str_index ]:

                if line_split[ str_index ].endswith( '"' ):
                    str_len = len( line_split[ str_index ] )
                    line_split[ str_index ] = line_split[ str_index ][ 1 : str_len-1 ]

                else:
                    quote = line_split[ str_index ][1:]
                    quote_str_index = str_index + 1
                    while line_split[ quote_str_index - 1 ].endswith( '\\"' ) or not line_split[ quote_str_index - 1 ].endswith( '"' ):

                        quote = quote + " " + line_split[ quote_str_index ]
                        line_split[ str_index ] = quote
                        del line_split[ quote_str_index ]

                    if '\\"' in line_split[ str_index ]:
                        # replace '\\"' with '"'
                        line_split[ str_index ] = '"'.join( line_split[ str_index ].split( '\\"' ) )

                    line_split[ str_index ] = line_split[ str_index ][:-1]

            str_index += 1

    return line_split


def CleanUpSplitLine( line_split ):
    
    line_split = RemoveQuotes( line_split )

    str_index = -1
    while str_index < len( line_split ) - 1:
        str_index += 1
            
        # remove any empty parts of the line
        if line_split[ str_index ] == '':
            del line_split[ str_index ]
            str_index -= 1
            continue

    line_split = JoinConditionalLine( line_split )

    return line_split


def JoinConditionalLine( line_split ):

    cond_line = GetConditionalLine( line_split )

    # get rid of the conditional from the line
    if cond_line != None:

        for string in line_split:
            if "[" in string:
                line_split = line_split[ :line_split.index(string) ]
                line_split.append( cond_line )
                break

    return line_split


def GetConditionalLine( line_split ):

    found_cond = False

    for string in line_split:
        if "[" in string or "]" in string:
            found_cond = line_split.index( string )
            break

    if found_cond != False:
        line = ''.join(line_split)
        cond_line = "[" + ( line.split( "[" )[1] ).split( "]" )[0] + "]"
        return cond_line

    return None


def GetAllDictValues( d ):
    found_values = []
    for k, v in d.items():
        if isinstance(v,dict):
            found_values.extend( GetAllDictValues(v) )
        else:
            # return found_values
            found_values.append( v )
    return found_values

