# pyOCD debugger
# Copyright (c) 2019-2020 Arm Limited
# SPDX-License-Identifier: Apache-2.0
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
from __future__ import print_function

import argparse
import os
import sys
import traceback
import logging

from pyocd.core.helpers import ConnectHelper
from pyocd.probe.pydapaccess import DAPAccess
from pyocd.core.memory_map import MemoryType

from test_util import (
    Test,
    TestResult,
    get_session_options,
    get_target_test_params,
    get_test_binary_path,
    PYOCD_DIR,
    )

GDB_TEST_BIN = "src/gdb_test_program/gdb_test.bin"
GDB_TEST_ELF = "src/gdb_test_program/gdb_test.elf"

class DebugContextTestResult(TestResult):
    def __init__(self):
        super(DebugContextTestResult, self).__init__(None, None, None)
        self.name = "debug_context"

class DebugContextTest(Test):
    def __init__(self):
        super(DebugContextTest, self).__init__("Debug Context Test", debug_context_test)

    def run(self, board):
        try:
            result = self.test_function(board.unique_id)
        except Exception as e:
            result = DebugContextTestResult()
            result.passed = False
            print("Exception %s when testing board %s" % (e, board.unique_id))
            traceback.print_exc(file=sys.stdout)
        result.board = board
        result.test = self
        return result

def debug_context_test(board_id):
    with ConnectHelper.session_with_chosen_probe(unique_id=board_id, **get_session_options()) as session:
        board = session.board
        target = session.target

        test_params = get_target_test_params(session)
        session.probe.set_clock(test_params['test_clock'])

        memory_map = target.get_memory_map()
        boot_region = memory_map.get_boot_memory()
        ram_region = memory_map.get_default_region_of_type(MemoryType.RAM)
        ram_base = ram_region.start
        binary_file = get_test_binary_path(board.test_binary)
        gdb_test_binary_file = os.path.join(PYOCD_DIR, GDB_TEST_BIN)

        # Read the gdb test binary file.
        with open(gdb_test_binary_file, "rb") as f:
            gdb_test_binary_data = list(bytearray(f.read()))

        test_pass_count = 0
        test_count = 0
        result = DebugContextTestResult()
        
        target.reset_and_halt()
        
        # Reproduce a gdbserver failure.
        print("\n------ Test 1: Mem cache ------")
        
        ctx = target.get_target_context()

        print("Writing gdb test binary")
        ctx.write_memory_block8(ram_base, gdb_test_binary_data)
        
        print("Reading first chunk")
        data = ctx.read_memory_block8(ram_base, 64)
        if data == gdb_test_binary_data[:64]:
            test_pass_count += 1
            print("TEST PASSED")
        else:
            print("TEST FAILED")
        test_count += 1
            
        print("Reading N chunks")
        did_pass = True
        for n in range(8):
            offset = 0x7e + (4 * n)
            data = ctx.read_memory_block8(ram_base + offset, 4)
            if data == gdb_test_binary_data[offset:offset + 4]:
                test_pass_count += 1
            else:
                did_pass = False
            test_count += 1
        if did_pass:
            print("TEST PASSED")
        else:
            print("TEST FAILED")

        print("\nTest Summary:")
        print("Pass count %i of %i tests" % (test_pass_count, test_count))
        if test_pass_count == test_count:
            print("DEBUG CONTEXT TEST PASSED")
        else:
            print("DEBUG CONTEXT TEST FAILED")

        # Clean up.
        target.reset()

        result.passed = test_count == test_pass_count
        return result

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='pyOCD debug context test')
    parser.add_argument('-d', '--debug', action="store_true", help='Enable debug logging')
    parser.add_argument("-da", "--daparg", dest="daparg", nargs='+', help="Send setting to DAPAccess layer.")
    args = parser.parse_args()
    level = logging.DEBUG if args.debug else logging.INFO
    logging.basicConfig(level=level)
    DAPAccess.set_args(args.daparg)
    # Set to debug to print some of the decisions made while flashing
    session = ConnectHelper.session_with_chosen_probe(**get_session_options())
    test = DebugContextTest()
    result = [test.run(session.board)]

