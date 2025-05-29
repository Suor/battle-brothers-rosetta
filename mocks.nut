::Hooks <- {
    function register(_id, _version, _name) {
        return {
            function require(...) {}
            function queue(...) {}
        }
    }
    QueueBucket = {
        Late = 4
    }
    SQClass = {
        ModVersion = function (_version) {
            return ::std.Str.split(".", _version).reduce(@(a, b) a.tointeger() * 1000 + b.tointeger())
        }
    }
}

::Const.Strings <- {}
::Const.Strings.EntityName <- [
    "Некромант"
]
::Const.Items <- {}
::Const.Items.WeaponType <- {}

::std.Debug.DEFAULTS.html = false;
