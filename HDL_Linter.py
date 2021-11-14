#######################################################################################################################
# HDL_Linter - Verilog and SystemVerilog linting with Sublime Text 4                                                  #
# Copyright (C) 2021  Dawid Szulc                                                                                     #
#                                                                                                                     #
# This program is free software: you can redistribute it and/or modify                                                #
# it under the terms of the GNU General Public License as published by                                                #
# the Free Software Foundation, either version 3 of the License, or                                                   #
# (at your option) any later version.                                                                                 #
#                                                                                                                     #
# This program is distributed in the hope that it will be useful,                                                     #
# but WITHOUT ANY WARRANTY; without even the implied warranty of                                                      #
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the                                                       #
# GNU General Public License for more details.                                                                        #
#                                                                                                                     #
# You should have received a copy of the GNU General Public License                                                   #
# along with this program.  If not, see <https://www.gnu.org/licenses/>.                                              #
#######################################################################################################################

import collections
import datetime
import os
import re
import shutil
import sublime
import sublime_plugin
import subprocess

class SublimeModified(sublime_plugin.EventListener):

    def on_modified_async(self, view):
        '''Called after changes have been made to the view. Runs in a separate thread, and does not block the
        application.

        :param view: Represents a view into a text buffer
        :type view: sublime.View
        '''
        # Update current status
        HDL_linter.modified_time = datetime.datetime.now().timestamp()
        HDL_linter.modified_view = view
        # Get settings
        settings.reload()
        delay = settings.delay()
        # Track modifications
        sublime.set_timeout_async(HDL_linter.track_modifications, 1050 * delay)

    def on_selection_modified_async(self, view):
        '''Called after the selection has been modified in the view. Runs in a separate thread, and does not block the
        application.

        :param view: Represents a view into a text buffer
        :type view: sublime.View
        '''
        # Find regions
        found = False
        view_id = view.id()
        if view_id in HDL_linter.error_list or view_id in HDL_linter.warning_list:
            selections = view.sel()
            if len(selections) == 1:
                selection = selections[0]
                error_regions = view.get_regions('HDL_Linter_error')
                warning_regions = view.get_regions('HDL_Linter_warning')
                for key, region in enumerate(error_regions):
                    if region.contains(selection):
                        view.set_status(
                            'hdl_status', HDL_linter.error_list[view_id][key]
                        )
                        found = True
                for key, region in enumerate(warning_regions):
                    if region.contains(selection):
                        view.set_status(
                            'hdl_status', HDL_linter.warning_list[view_id][key]
                        )
                        found = True
        if not found:
            view.erase_status('hdl_status')


class HDL_linter:
    '''Verilog and SystemVerilog linting with Sublime Text 4
    '''

    def __init__(self):
        '''Initialization
        '''
        self.modified_time = datetime.datetime.now().timestamp()  # Time of last modification
        self.compiled_time = datetime.datetime.now().timestamp()  # Time of last compilation
        self.modified_view = None  # Tast modified view
        self.error_list = {}  # List of errors for each view
        self.warning_list = {}  # List of warnings for each view

    def track_modifications(self):
        '''Check if the content of the file has changed
        '''
        if self.modified_time > self.compiled_time:
            now = datetime.datetime.now().timestamp()
            # Get settings
            settings.reload()
            delay = settings.delay()
            # Check changes
            if (now - self.modified_time) > 0.95 * delay:
                self.compiled_time = self.modified_time
                view = self.modified_view
                if type(view) == sublime.View:
                    head, tail, ext = self.get_os_path(view)
                    if ext in ['.v', '.vh', '.sv', '.svh']:
                        self.init_linter(view, head, tail, ext)
                        self.linter.prepare()
                        output = self.linter.get_output()
                        errors, warnings = self.linter.parse_output(output)
                        self.linter.clean()
                        self.update_selections(view, errors, warnings)

    def get_os_path(self, view):
        '''Returns some useful data on pathnames

        :param view: Represents a view into a text buffer
        :type view: sublime.View
        :return (Everything leading up to last pathname component, Last pathname component, Extension)
        :rtype: (str, str, str)
        '''
        head, tail, ext = ('', '', '')
        file_name = view.file_name()
        if file_name is not None:
            ext = os.path.splitext(file_name)[1].lower()
            head, tail = os.path.split(file_name)
        return head, tail, ext

    def init_linter(self, view, head, tail, ext):
        '''Initialize selected linter

        :param view: Represents a view into a text buffer
        :type view: sublime.View
        :param head: Everything leading up to last pathname component
        :type head: str
        :param tail: Last pathname component
        :type tail: str
        :param ext: Extension
        :type ext: str
        '''
        # Get settings
        if ext in ['.v', '.vh']:
            linter = settings.verilog_linter()
        if ext in ['.sv', '.svh']:
            linter = settings.systemverilog_linter()
        # Select linter
        if linter == 'vivado':
            self.linter = vivado(view, head, tail, ext)
        if linter == 'questasim':
            self.linter = questasim(view, head, tail, ext)

    def update_selections(self, view, errors, warnings):
        '''Update error regions and warning regions
        '''
        # Get error regions
        errors = collections.OrderedDict(sorted(errors.items()))
        self.error_list[view.id()] = []
        for error_description in errors.values():
            self.error_list[view.id()].append(error_description)
        error_positions = []
        for error_position in errors.keys():
            offset = view.text_point(error_position - 1, 0)
            error_position = view.line(offset)
            error_positions.append(error_position)
        # Erase old error regions
        view.erase_regions('HDL_Linter_error')
        # Add new error regions
        view.add_regions(
            'HDL_Linter_error', error_positions, 'region.redish', 'bookmark', sublime.DRAW_NO_FILL
        )
        # Get warning regions
        warnings = collections.OrderedDict(sorted(warnings.items()))
        self.warning_list[view.id()] = []
        for warning_description in warnings.values():
            self.warning_list[view.id()].append(warning_description)
        warning_positions = []
        for warning_position in warnings.keys():
            offset = view.text_point(warning_position - 1, 0)
            warning_position = view.line(offset)
            warning_positions.append(warning_position)
        # Erase old warning regions
        view.erase_regions('HDL_Linter_warning')
        # Add new warning regions
        view.add_regions(
            'HDL_Linter_warning', warning_positions, 'region.yellowish', 'bookmark', sublime.DRAW_NO_FILL
        )
        # Show selected region
        SublimeModified.on_selection_modified_async(self, view)

class vivado:
    '''Lint HDL with Xilinx Vivado'''

    def __init__(self, view, head, tail, ext):
        '''Initialization

        :param view: Represents a view into a text buffer
        :type view: sublime.View
        :param head: Everything leading up to last pathname component
        :type head: str
        :param tail: Last pathname component
        :type tail: str
        :param ext: Extension
        :type ext: str
        '''
        self.view = view  # Represents a view into a text buffer
        self.head = head  # Everything leading up to last pathname component
        self.tail = tail  # Last pathname component
        self.ext = ext  # Extension
        self.cache_file_path = f"{os.path.join(self.head, self.tail)}.sublime-cache"  # Cache file pathname

    def prepare(self):
        '''Prepare view content
        '''
        # Get file content
        sublime_region = sublime.Region(0, self.view.size())
        content = self.view.substr(sublime_region).rstrip()
        # Resolve issue with root scope declaration in verilog header file
        if self.ext == '.vh':
            while content.rfind('//') > content.rfind('\n'):
                content = content[:content.rfind('//')].rstrip()
            content = f"module HDL_Linter;\n{content}\nendmodule\n"
        # Create cache file
        try:
            with open(self.cache_file_path, 'w', encoding='utf-8') as cache_file:
                cache_file.write(content)
        except OSError:
            print(f"HDL_Linter: Can\'t create and open `{self.cache_file_path}` file.")

    def get_output(self):
        '''Compiles Verilog source code, SystemVerilog source code and returns output

        :return Compilation output
        :rtype: str
        '''
        cmd = self.get_xvlog_cmd()
        exitcode, output = subprocess.getstatusoutput(cmd)
        if exitcode:
            print('HDL_Linter: Process `xvlog` returns a non-zero return code.')
        return output

    def get_xvlog_cmd(self):
        '''Create xvlog command

        :return xvlog command
        :rtype: list of str
        '''
        # Get settings
        vivado_bin_dir = settings.vivado_bin_dir()
        # Create cmd
        cmd = []
        path = os.path.join(vivado_bin_dir, 'xvlog')
        cmd.append(path)  # Vivado compiler
        cmd.append(self.cache_file_path)  # Soruce file 
        cmd.append('--nosignalhandlers')  # Run with no XSim specific signal handlers
        cmd.append('--nolog')  # Suppress log file generation
        cmd.append('--verbose')  # Specify verbosity level for printing messages
        cmd.append('2')  # Low verbosity
        # # Enable SystemVerilog features and keywords
        if self.ext in ['.sv', '.svh']:
            cmd.append('--sv')
        return cmd

    def parse_output(self, output):
        '''Parse compilation output

        :param output: Compilation output
        :type output: str
        :return Errors and warnings
        :rtype: (list of errors, list of warnings)
        '''
        errors = {}  # Dictionary of errors
        warnings = {}  # Dictionary of warnings
        includes = {}  # Dictionary of includes

        # Parse
        lines = output.splitlines()
        for line in lines:
            msg = {}  # Message
            # Find valid message
            match = re.match(r'(\w+): \[VRFC \d+-\d+\]', line)
            if match:
                msg['level'] = match.group(1)
                match_pos = len(match.group(0)) + 1
                line = line[match_pos:]
                match = re.match(r'\](\d+):([^\[])+\[', line[::-1])
                if match:
                    msg['file_line'] = int(match.group(1)[::-1])
                    msg['file_name'] = match.group(2)[::-1]
                    match_pos = len(match.group(0))
                    line = line[:-match_pos]
                    msg['content'] = line
                    # Resolve issue with root scope declaration in verilog header file
                    if self.ext == '.vh':
                        if msg['file_line'] == 1:
                            continue
                        if msg['content'].find('keyword endmodule') != -1:
                            msg['content'] = 'unexpected EOF'
                            msg['file_line'] -= 1
                        if msg['content'].find('syntax error near \'endmodule\'') != -1:
                            continue
                        msg['file_line'] -= 1
                    # Handle error
                    if msg['level'] == 'ERROR':
                        pos = includes.get(msg['file_name'])
                        if pos is not None:
                            msg['file_line'] = pos
                        if msg['file_line'] in errors.keys():
                            errors[msg['file_line']] += f" | {msg['content']}"
                        else:
                            errors[msg['file_line']] = msg['content']
                    # Handle warning
                    if msg['level'] == 'WARNING':
                        pos = includes.get(msg['file_name'])
                        if pos is not None:
                            msg['file_line'] = pos
                        if msg['file_line'] in warnings.keys():
                            warnings[msg['file_line']] += f" | {msg['content']}"
                        else:
                            warnings[msg['file_line']] = msg['content']
                    # Handle include
                    if msg['level'] == 'INFO':
                        match = re.search(
                            'Compiling verilog file \"([^\"]+)\" included at line [0-9]+', msg['content']
                        )
                        if match:
                            file_name = match.group(1)
                            pos = includes.get(msg['file_name'])
                            if pos is not None:
                                includes[file_name] = pos
                            else:
                                includes[file_name] = msg['file_line']
        return errors, warnings

    def clean(self):
        '''Remove temporary files
        '''
        # Remove cache file
        try:
            os.remove(self.cache_file_path)
        except OSError:
            print(f"HDL_Linter: Can\'t remove `{self.cache_file_path}` file.")
        # Remove compilation file
        path = os.path.join(os.getcwd(), 'xvlog.pb')
        try:
            os.remove(path)
        except OSError:
            print(f"HDL_Linter: Can\'t remove `{path}` file.")
        # Remove compilation library
        path = os.path.join(os.getcwd(), 'xsim.dir')
        try:
            shutil.rmtree(path)
        except OSError:
            print(f"HDL_Linter: Can\'t remove `{path}` directory.")

class questasim:
    '''Lint HDL with Intel Questasim'''

    def __init__(self, view, head, tail, ext):
        '''Initialization

        :param view: Represents a view into a text buffer
        :type view: sublime.View
        :param head: Everything leading up to last pathname component
        :type head: str
        :param tail: Last pathname component
        :type tail: str
        :param ext: Extension
        :type ext: str
        '''
        self.view = view  # Represents a view into a text buffer
        self.head = head  # Everything leading up to last pathname component
        self.tail = tail  # Last pathname component
        self.ext = ext  # Extension
        self.cache_file_path = f"{os.path.join(self.head, self.tail)}.sublime-cache"  # Cache file pathname

    def prepare(self):
        '''Prepare view content
        '''
        # Get file content
        sublime_region = sublime.Region(0, self.view.size())
        content = self.view.substr(sublime_region).rstrip()
        # Create library
        cmd = self.get_vlib_cmd()
        exitcode, output = subprocess.getstatusoutput(cmd)
        if exitcode:
            print('HDL_Linter: Process `vlib` returns a non-zero return code.')
        # Create cache file
        try:
            with open(self.cache_file_path, 'w', encoding='utf-8') as cache_file:
                cache_file.write(content)
        except OSError:
            print(f"HDL_Linter: Can\'t create and open `{self.cache_file_path}` file.")

    def get_vlib_cmd(self):
        '''Create vlib command

        :return vlib command
        :rtype: list of str
        '''
        # Get settings
        questasim_bin_dir = settings.questasim_bin_dir()
        # Create cmd
        cmd = []
        path = os.path.join(questasim_bin_dir, 'vlib')
        cmd.append(path)  # Questasim library
        cmd.append('-nocompress')  # Disable compression
        cmd.append('work')  # Library name
        return cmd

    def get_output(self):
        '''Compiles Verilog source code, SystemVerilog source code and returns output

        :return Compilation output
        :rtype: str
        '''
        cmd = self.get_vlog_cmd()
        exitcode, output = subprocess.getstatusoutput(cmd)
        if exitcode:
            print('HDL_Linter: Process `vlog` returns a non-zero return code.')
        return output

    def get_vlog_cmd(self):
        '''Create vlog command

        :return vlog command
        :rtype: list of str
        '''
        # Get settings
        questasim_bin_dir = settings.questasim_bin_dir()
        # Create cmd
        cmd = []
        path = os.path.join(questasim_bin_dir, 'vlog')
        cmd.append(path)  # Questasim compiler
        cmd.append(self.cache_file_path)  # Source file
        cmd.append('-work')  # Specify work library
        cmd.append('work')  # Library name
        cmd.append('-O0')  # Perform lint-style check
        cmd.append('-lint=full')  # Perform lint-style check
        cmd.append('-pedanticerrors')  # Enforce strict language checks
        cmd.append('-msgsingleline')  # Display the messages in a single line
        # Enable SystemVerilog features and keywords
        if self.ext in ['.sv', '.svh']:
            cmd.append('-sv')
        # Ensure compatibility with IEEE Std 1364
        if self.ext in ['.v', '.vh']:
            compatibility = settings.verilog_compatibility()
            if compatibility == 2001:
                cmd.append('-vlog01compat')
            if compatibility == 1995:
                cmd.append('-vlog95compat')
        #  Ensure compatibility with IEEE Std 1800
        if self.ext in ['.sv', '.svh']:
            compatibility = settings.verilog_compatibility()
            if compatibility == 2017:
                cmd.append('-sv17compat')
            if compatibility == 2012:
                cmd.append('-sv12compat')
            if compatibility == 2009:
                cmd.append('-sv09compat')
            if compatibility == 2005:
                cmd.append('-sv05compat')
        return cmd

    def parse_output(self, output):
        '''Parse compilation output

        :param output: Compilation output
        :type output: str
        :return Errors and warnings
        :rtype: (list of errors, list of warnings)
        '''
        errors = {}  # dict of errors
        warnings = {}  # dict of warnings

        lines = output.splitlines()
        for line in lines:
            msg = {}  # Message
            # Find valid message
            match = re.match(r'\*\* ([\w]+):', line)
            if match:
                msg['level'] = match.group(1)
                match_pos = len(match.group(0)) + 1
                line = line[match_pos:]
                match = re.match(r'\([^\)]+\)', line)
                if match:
                    match_pos = len(match.group(0)) + 1
                    line = line[match_pos:]
                match = re.match(r'([^\(]+)\((\d+)\):', line)
                if not match:
                    match = re.match(r'\*\* while parsing .* at ([^\(]+)\((\d+)\).+\):', line)
                if match:
                    msg['file_name'] = match.group(1)
                    msg['file_line'] = int(match.group(2))
                    match_pos = len(match.group(0)) + 1
                    line = line[match_pos:]
                    match = re.match(r'\([^\)]+\)', line)
                    if match:
                        match_pos = len(match.group(0)) + 1
                        line = line[match_pos:]
                    msg['content'] = line
                    # Handle error
                    if msg['level'] == 'Error':
                        if msg['file_line'] in errors.keys():
                            errors[msg['file_line']] += f" | {msg['content']}"
                        else:
                            errors[msg['file_line']] = msg['content']
                    # Handle warning
                    if msg['level'] == 'Warning':
                        if msg['file_line'] in warnings.keys():
                            warnings[msg['file_line']] += f" | {msg['content']}"
                        else:
                            warnings[msg['file_line']] = msg['content']
        return errors, warnings

    def clean(self):
        '''Remove temporary files
        '''
        # Remove cache file
        try:
            os.remove(self.cache_file_path)
        except OSError:
            print(f"HDL_Linter: Can\'t remove `{self.cache_file_path}` file.")
        # Remove compilation library
        path = os.path.join(os.getcwd(), 'work')
        try:
            shutil.rmtree(path)
        except OSError:
            print(f"HDL_Linter: Can\'t remove `{path}` directory.")


class HDL_Linter_settings:
    '''Handle HDL_Linter settings
    '''

    def __init__(self):
        '''Load settings from file
        '''
        self.settings = sublime.load_settings('HDL_Linter.sublime-settings')

    def reload(self):
        '''Reload settings from file
        '''
        self.settings = sublime.load_settings('HDL_Linter.sublime-settings')

    def delay(self):
        '''Minimum delay in seconds before linter run
        '''
        # Get setting
        setting = self.settings.get('delay')
        # Possible values: int, float
        if type(setting) == float or type(setting) == int:
            return setting
        # Default value: 0.5
        setting = 0.5
        print(f"HDL_Linter: `delay` changed to default value `{setting}`")
        return setting

    def verilog_linter(self):
        '''Software used to lint Verilog files
        '''
        # Get setting
        setting = self.settings.get('verilog_linter')
        # Possible values: {"vivado", "questasim"}
        if type(setting) == str:
            setting = setting.lower()
            if setting in ['vivado', 'questasim']:
                return setting
        # Default value: "vivado"
        setting = 'vivado'
        print(f"HDL_Linter: `verilog_linter` changed to default value `{setting}`")
        return setting

    def systemverilog_linter(self):
        '''Software used to lint SystemVerilog files
        '''
        # Get setting
        setting = self.settings.get('systemverilog_linter')
        # Possible values: {"vivado", "questasim"}
        if type(setting) == str:
            setting = setting.lower()
            if setting in ['vivado', 'questasim']:
                return setting
        # Default value: "vivado"
        setting = 'vivado'
        print(f"HDL_Linter: `systemverilog_linter` changed to default value `{setting}`")
        return setting

    def vivado_bin_dir(self):
        '''Directory with Vivado's xvlog (when not added to path)
        '''
        # Get setting
        setting = self.settings.get('vivado_bin_dir')
        # Possible values: "<path>"
        if type(setting) == str:
            return setting
        # Default value: ""
        setting = ''
        return setting

    def questasim_bin_dir(self):
        '''Directory with Questasim's vlog (when not added to path)
        '''
        # Get setting
        setting = self.settings.get('questasim_bin_dir')
        # Possible values: "<path>"
        if type(setting) == str:
            return setting
        # Default value: ""
        setting = ''
        return setting

    def verilog_compatibility(self):
        '''Ensure compatibility with IEEE Std 1364
        '''
        # Get setting
        setting = self.settings.get('verilog_compatibility')
        # Possible values: {1995, 2001, 2005}
        if type(setting) == int:
            if setting in [1995, 2001, 2005]:
                return setting
        # Default value: 2005
        setting = 2005
        print(f"HDL_Linter: `verilog_compatibility` changed to default value `{setting}`")
        return setting

    def systemverilog_compatibility(self):
        '''Ensure compatibility with IEEE Std 1800
        '''
        # Get setting
        setting = self.settings.get('systemverilog_compatibility')
        # Possible values: {2005, 2009, 2012, 2017}
        if type(setting) == int:
            if setting in [2005, 2009, 2012, 2017]:
                return setting
        # Default value: 2005
        setting = 2017
        print(f"HDL_Linter: `systemverilog_compatibility` changed to default value `{setting}`")
        return setting


settings = HDL_Linter_settings()
HDL_linter = HDL_linter()
