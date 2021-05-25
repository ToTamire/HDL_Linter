# HDL_Linter
Verilog and SystemVerilog linting with Sublime Text 4

![assign](https://user-images.githubusercontent.com/71039587/119546834-a7071200-bd94-11eb-9f11-88dd92b04342.gif)

# The repository owners are:
- Dawid Szulc dawidszulc094@gmail.com

# Instalation:
- Press ```CTRL``` + ```SHIFT``` + ```p```
- Select ```Package Control: Add Repository```
- Paste ```https://github.com/ToTamire/HDL_Linter``` to input box wich appear on bottom
- Confirm with ```Enter```
- Press again ```CTRL``` + ```SHIFT``` + ```p```
- Select ```Package Control: Install Package```
- Select ```HDL_Linter```

If you don't have Vivado's xvlog added to path:
- Press ```Preferences```
- Press ```Package Settings```
- Press ```HDL_Linter```
- Press ```Settings - User```
- Add ```HDL_Linter_xvlog_dir``` with your xvlog dir to settings:
```
{
	"HDL_Linter_xvlog_dir": "<xvlog_dir>",
}
```
for example:
```
{
	"HDL_Linter_xvlog_dir": "C:/Xilinx/Vivado/2019.1/bin/",
}
```
- Save settings file with ```CTRL``` + ```s```

# Known issues:
- Verilog header files (*.vh) are linted as SystemVerilog because of root scope declarations
