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

import sublime
import sublime_plugin
import datetime
import subprocess
import collections
import re
import os


class HDL_linter:
    ''' Verilog and SystemVerilog linting with Sublime Text 4 '''

    def __init__(self):
        ''' HDL_linter initialization '''
        self.modified_time = datetime.datetime.now().timestamp()  # set time of last modification to current
        self.compiled_time = datetime.datetime.now().timestamp()  # set time of last compilation to current
        self.modified_view = None  # set last modified view to none

        self.error_list = {}  # list of errors for each view
        self.warning_list = {}  # list of warnings for each view

        self.track_modifications()  # start tracking modifications

    def track_modifications(self):
        ''' track file modifications '''
        if self.modified_time > self.compiled_time:  # if last modification of view occur after last compilation of view
            now = datetime.datetime.now().timestamp()  # get current time
            delay = self.get_delay()  # get delay from settings
            if (now - self.modified_time) > delay:  # if user end modifications
                self.compiled_time = self.modified_time
                view = self.modified_view  # get last modified view
                if type(view) == sublime.View:  # if view is correct
                    file = self.get_file(view)  # get file
                    if file is not False:  # if file is correct
                        cache_file = self.create_cache_file(view, file)  # create cache file
                        if cache_file is not False:  # if cache file is correct
                            output = self.get_xvlog_output(file)  # get output from xvlog
                            self.remove_cache_file(file)  # remove cache file
                            errors, warnings = self.parse_xvlog_output(view, output, file)  # parse output from xvlog
                            self.print_selections(view, errors, warnings)  # print selections in modified view
        sublime.set_timeout_async(self.track_modifications, 100)  # wait some time and repeat

    def get_delay(self):
        ''' get linting delay '''
        settings = sublime.load_settings('HDL_Linter.sublime-settings')  # get settings
        delay = settings.get('HDL_Linter_delay')  # get user defined delay
        if delay is None:  # if delay is not in settings
            delay = 0.5  # set delay to default value
        if (type(delay) != int and type(delay) != float) or delay < 0:  # if delay has wrong value
            delay = 0.5  # set delay to default value
        return delay  # return correct delay value

    def get_file(self, view):
        ''' get file info '''
        file_name = view.file_name()  # get name of modivied file
        if file_name is not None:  # check if file exist out of sublime
            file_name = file_name.replace('\\', '/')  # change path separator to Unix compliant
            extension = os.path.splitext(file_name)[1][1:]  # get extension
            extension = extension.lower()  # set extension to lowercase
            if extension in ['v', 'vh', 'sv', 'svh']:  # if file has HDL extension
                return {  # return handsome file info
                    'file_name': file_name,  # file name with directory
                    'extension': extension,  # file extension
                }
        return False  # if something goes wrong return false

    def create_cache_file(self, view, file):
        ''' create chache file '''
        view_size = view.size()  # get size of view
        sublime_region = sublime.Region(0, view_size)  # get region of view
        content = view.substr(sublime_region)  # get content of view
        content = content.rstrip()  # remove ending whitespaces
        if file['extension'] == 'vh':  # if file is verilog header
            if content.find('//') > content.rfind('\n'):  # if file ends with single line comment
                content = content[:content.find('//')]  # remove signle line comment
            content = f"module HDL_Linter;\n{content} endmodule\n"  # set content inside pseudo module
        with open(f"{file['file_name']}.sublime-cache", 'w', encoding='utf-8') as cache_file:  # create cache file
            cache_file.write(content)  # write content of view to cache file
        if os.path.isfile(f"{file['file_name']}.sublime-cache"):  # if file was successfuly created
            return True  # return true
        return False  # if something goes wrong return false

    def get_xvlog_dir(self):
        ''' get xvlog dir from settings '''
        settings = sublime.load_settings('HDL_Linter.sublime-settings')  # get settings
        xvlog_dir = settings.get('HDL_Linter_xvlog_dir')  # get xvlog dir from settings
        if xvlog_dir is None or type(xvlog_dir) != str or xvlog_dir == '':  # if xvlog directory has wrong value
            return ''  # assume that folder containing xvlog is added to path
        else:  # if xvlog dir is in settings
            xvlog_dir = xvlog_dir.replace('\\', '/')  # change path separator to Unix compliant
            if xvlog_dir[-1] == '/':  # if user dont end path with slash
                xvlog_dir += '/'  # append slash
            return xvlog_dir  # return xvlog directory

    def get_xvlog_output(self, file):
        ''' get output from xvlog '''
        process = []  # create list of process parameters
        xvlog_dir = self.get_xvlog_dir()  # get xvlog dir from settings
        process.append(f"{xvlog_dir}xvlog")  # xvlog command
        process.append(f"{file['file_name']}.sublime-cache")  # append cache file
        process.append('--nosignalhandlers')  # necessary when 3rd party software causing a crash
        process.append('--nolog')  # suppress log file generation
        process.append('--verbose')  # verbosity level for printing messages
        process.append('2')  # set to minimum
        if file['extension'] in ['sv', 'svh']:  # if file has System Verilog extension
            process.append('--sv')  # compile in System Verilog mode
        return subprocess.getoutput(process)  # return output

    def remove_cache_file(self, file):
        ''' remove cache file '''
        os.remove(f"{file['file_name']}.sublime-cache")  # remove cache file

    def parse_xvlog_output(self, view, output, top_file_name):
        ''' parse output from xvlog '''
        errors = {}  # create dict of errors
        warnings = {}  # create dict of warnings
        includes = {}  # create dict of includes

        lines = output.splitlines()  # split output it into lines
        for line in lines:  # for line in output lines
            match = re.findall(
                '([A-Za-z0-9]+)(:)( \[)VRFC([^\]]+)(\] )([^\[]+)(\[)([^\]]+)(\])', line
            )  # match all notifications
            if len(match) == 1 and len(match[0]) == 9:  # if  found
                file_name = match[0][7].rsplit(':', 1)  # split file to name and position
                if len(file_name) == 2:  # if file has name and position
                    pos = int(file_name[1].strip())  # remove leading and trailing whitespaces
                    file_name = file_name[0].strip()  # remove leading and trailing whitespaces
                    match = {  # make match handsome
                        'type': match[0][0].strip(),  # match type
                        'descr': match[0][5].strip(),  # match description
                        'file_name': file_name,  # file name with directory
                        'pos': pos,  # match position
                    }
                    if top_file_name['extension'] == 'vh':  # if file is verilog header
                        if match['pos'] == 1:  # if notification is in line with pseudo module keyword
                            continue  # skip this notification
                        if match['descr'].find('keyword endmodule') != -1:  # if notification is unexpected endmodule
                            match['descr'] = 'unexpected EOF'  # change description to unexpected end of file
                        if match['descr'].find('syntax error near \'endmodule\'') != -1:  # if other endmodule notification
                            continue  # skip this notification
                        match['pos'] -= 1  # substract position by pseudo module declaration in first line
                    if match['type'] == 'ERROR':  # if notification is error
                        pos = includes.get(file_name)  # get include position
                        if pos is not None:  # if match is in include file
                            match['pos'] = pos  # change position to include position
                        if match['pos'] in errors.keys():  # if there is already error with same position
                            errors[match['pos']] += f" | {match['descr']}"  # add next error description
                        else:
                            errors[match['pos']] = match['descr']  # add new error
                    if match['type'] == 'WARNING':  # if notification is warning
                        pos = includes.get(file_name)  # get include position
                        if pos is not None:  # if match is in include file
                            match['pos'] = pos  # change position to include position
                        if match['pos'] in warnings.keys():  # if there is already warning with same position
                            warnings[match['pos']] += f" | {match['descr']}"  # add next warning description
                        else:
                            warnings[match['pos']] = match['descr']  # add new warning
                    if match['type'] == 'INFO':  # if notification is info
                        match2 = re.findall(
                            '(Compiling verilog file \")([^\"]+)(\" included at line [0-9]+)', match['descr']
                        )  # match included file
                        if len(match2) == 1 and len(match2[0]) == 3:  # if file is included
                            file_name = match2[0][1]  # get file name from match
                            pos = includes.get(match['file_name'])  # get parent include position
                            if pos is not None:  # if parent is not top file
                                includes[file_name] = pos  # set include position to parent include position
                            else:  # if parent is top file
                                includes[file_name] = match['pos']  # set include position to match
        return errors, warnings  # return parsed outptu from xvlog

    def print_selections(self, view, errors, warnings):
        ''' print selections in modified view '''
        errors = collections.OrderedDict(sorted(errors.items()))  # sort errors by line
        self.error_list[view.id()] = []  # erase list of old errors in modified view
        for error_description in errors.values():  # for each error
            self.error_list[view.id()].append(error_description)  # append error description to list of errors
        error_positions = []  # list of error positions
        for error_position in errors.keys():  # for each error
            offset = view.text_point(error_position - 1, 0)  # convert row to buffer offset
            error_position = view.line(offset)  # convert buffer offset to line region
            error_positions.append(error_position)  # append error positon to error positions
        view.erase_regions('HDL_Linter_error')  # erase old error regions from view
        view.add_regions(
            'HDL_Linter_error', error_positions, 'region.redish', 'bookmark', sublime.DRAW_NO_FILL
        )  # set all error regions to view
        warnings = collections.OrderedDict(sorted(warnings.items()))  # sort warnings by line
        self.warning_list[view.id()] = []  # erase list of warnings
        for warning_description in warnings.values():  # for warning description in warnings
            self.warning_list[view.id()].append(warning_description)  # append warning description to list of warnings
        warning_positions = []  # list of warning positions
        for warning_position in warnings.keys():  # for each warning
            offset = view.text_point(warning_position - 1, 0)  # convert row to buffer offset
            warning_position = view.line(offset)  # convert buffer offset to line region
            warning_positions.append(warning_position)  # append warning positon to warning positions
        view.erase_regions('HDL_Linter_warning')  # erase old warning regions from view
        view.add_regions(
            'HDL_Linter_warning', warning_positions, 'region.yellowish', 'bookmark', sublime.DRAW_NO_FILL
        )  # set all warning regions to view
        SublimeModified.on_selection_modified_async(self, view)  # show notification description to current selection


class SublimeModified(sublime_plugin.EventListener):  # check if file is modified

    def on_modified_async(self, view):  # when user modified view
        global HDL_linter

        HDL_linter.modified_time = datetime.datetime.now().timestamp()  # set last modified time to current
        HDL_linter.modified_view = view  # set last modified view to current

    def on_selection_modified_async(self, view):  # when user modified selection
        global HDL_linter

        found = False  # error or warning in selection not found
        view_id = view.id()  # get view id of modified selection
        # view_id = str(view_id)  # convert view id to str
        if view_id in HDL_linter.error_list or view_id in HDL_linter.warning_list:  # if view in list of errors or warnings
            selections = view.sel()  # get current selections
            if len(selections) == 1:  # if only one selection
                selection = selections[0]  # convert list of selections to selection
                error_regions = view.get_regions('HDL_Linter_error')  # get all error regions
                warning_regions = view.get_regions('HDL_Linter_warning')  # get all warning regions
                for key, region in enumerate(error_regions):  # for region in list of error regions
                    if region.contains(selection):  # if selection in region
                        view.set_status(
                            'hdl_status', HDL_linter.error_list[view_id][key]
                        )  # set error description to status bar
                        found = True  # error in selection found
                for key, region in enumerate(warning_regions):  # for region in list of warning regions
                    if region.contains(selection):  # if selection in region
                        view.set_status(
                            'hdl_status', HDL_linter.warning_list[view_id][key]
                        )  # set warning description to status bar
                        found = True  # warning in selection found
        if not found:  # if error or warning in selection not found
            view.erase_status('hdl_status')  # erase status bar


HDL_linter = HDL_linter()  # Initialize HDL_linter
