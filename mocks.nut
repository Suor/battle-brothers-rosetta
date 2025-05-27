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
}
::Const.Strings <- {}
::Const.Strings.EntityName <- [
    "Некромант"
]
::Const.Items <- {}
::Const.Items.WeaponType <- {}

::std.Debug.DEFAULTS.html = false;
