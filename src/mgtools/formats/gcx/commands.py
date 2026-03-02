from mgtools.formats.gcx.strcode import strcode

BUILTIN_COMMANDS: dict[int, str] = {
    strcode("if"): "if",
    strcode("switch"): "switch",
    strcode("eval"): "eval",
    strcode("call"): "call",
    strcode("return"): "return",
    strcode("print"): "print",
}

SCRIPT_COMMANDS: dict[int, str] = {
    strcode("mesg"): "mesg",
    strcode("command"): "command",
    strcode("chara"): "chara",
    strcode("trap"): "trap",
    strcode("load"): "load",
    strcode("map"): "map",
    strcode("restart"): "restart",
}
