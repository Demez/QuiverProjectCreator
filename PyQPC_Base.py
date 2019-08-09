
import sys
import os


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


def FindItem( value_list, item, return_value=False ):
    if item in value_list:
        if return_value:
            return value_list[ value_list.index( item ) ]
        else:
            return True
    else:
        return False


def FindItemValue( value_list, item, return_value=False ):
    if item in value_list:
        if return_value:
            return value_list[ value_list.index( item ) + 1 ]
        else:
            return True
    else:
        return False


def FindCommand( arg, return_value=False ):
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


def GetAllDictValues( d ):
    found_values = []
    for k, v in d.items():
        if isinstance(v,dict):
            found_values.extend( GetAllDictValues(v) )
        else:
            # return found_values
            found_values.append( v )
    return found_values


def CreateDirectory(directory):
    if not os.path.exists(directory):
        os.makedirs(directory)

