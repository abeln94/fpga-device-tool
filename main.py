import os
import subprocess

from CONFIG import VIVADO_BITSTREAM_LOAD
from UI import UI
from admin import run_as_admin
from fpgas import FPGAs
from vivado import Vivado


def main():
    # init
    vivado = Vivado()
    fpgas = FPGAs()

    class CustomUI(UI):
        def __init__(self):
            super().__init__(vivado.is_vivado_available())

            # do nothing by default, override for custom
            self.refresh = lambda: None
            self.autoRefresh = lambda: None
            self.bitstream = lambda: None
            self.preScript = lambda: None
            self.postScript = lambda: None

        # def utils
        def do_program(self):
            for command, _, parameter in self.steps_values:
                if command == 'pause':
                    self.wait("Paused")
                elif command == 'script':
                    subprocess.call(parameter)
                elif command == 'bitstream':
                    vivado.program(parameter)
                else:
                    print("Ignoring unknown programming command:", command, parameter)

        def _has_bitream_step(self):
            return any(c[0] == 'bitstream' for c in self.steps_values)

        def enableAll(self):
            def f():
                for i in fpgas:
                    self.step(f"Enabling board {i + 1}")
                    fpgas.enable(i)

            self.background(f, len(fpgas))

        def disableAll(self):
            def f():
                for i in fpgas:
                    self.step(f"Disabling board {i + 1}")
                    fpgas.disable(i)

            self.background(f, len(fpgas))

        def programAll(self):
            def f():
                states = fpgas.get_state()
                for i in fpgas:
                    self.step(f"Enabling board {i + 1}")
                    fpgas.enable(i)
                    for j in fpgas:
                        if j != i:
                            self.step(f"Disabling board {j + 1}")
                            fpgas.disable(j)
                    if i == 0 and self._has_bitream_step():
                        self.step("Initializing Vivado (may take a while)")
                        vivado.prepare()
                    self.step(f"Programming board {i + 1}")
                    self.do_program()
                for i, state in states:
                    self.step(f"Restoring {'enabled' if state else 'disabled'} board {i + 1}")
                    fpgas.toggle(i, state)

            self.background(f, len(fpgas) * (1 + (len(fpgas) - 1) + 1) + 1 + len(fpgas))

        def toggle(self, i):
            def f(i):
                if fpgas.enabled(i) is None:
                    self.step("Skipping")
                if fpgas.enabled(i):
                    self.step("Disabling")
                    fpgas.disable(i)
                else:
                    self.step("Enabling")
                    fpgas.enable(i)

            self.background(lambda: f(int(i)), 1)

        def enableOnly(self, i):
            def f(i):
                self.step("Enabling board")
                fpgas.enable(i)
                for j in fpgas:
                    if j != i:
                        self.step(f"Disabling board {j + 1}")
                        fpgas.disable(j)

            self.background(lambda: f(int(i)), 1 + (len(fpgas) - 1))

        def program(self, i):
            def f(i):
                states = fpgas.get_state()
                self.step("Enabling board")
                fpgas.enable(i)
                for j in fpgas:
                    if j != i:
                        self.step(f"Disabling board {j + 1}")
                        fpgas.disable(j)
                if self._has_bitream_step():
                    self.step("Initializing Vivado (may take a while)")
                    vivado.prepare()
                self.step("Programming board")
                self.do_program()

                for i, state in states:
                    self.step(f"Restoring {'enabled' if state else 'disabled'} board {i + 1}")
                    fpgas.toggle(i, state)

            self.background(lambda: f(int(i)), 1 + (len(fpgas) - 1) + 2 + len(fpgas))

        # steps

        def steps(self):
            selection = self.get_steps_selection()
            if selection is not None and selection >= len(self.steps_values):
                # remove selection
                self._update_steps(None)

        def stepsUp(self):
            self._change_selection(-1)

        def stepsRemove(self):
            self._change_selection(None)

        def stepsDown(self):
            self._change_selection(1)

        def _change_selection(self, offset):
            selection = self.get_steps_selection()
            if selection is None: return
            if offset:
                # swap
                new_selection = selection + offset
                if not (0 <= new_selection <= len(self.steps_values) - 1): return
                self.steps_values[selection], self.steps_values[new_selection] = self.steps_values[new_selection], self.steps_values[selection]
            else:
                # remove
                del self.steps_values[selection]
                new_selection = selection if selection < len(self.steps_values) else len(self.steps_values) - 1 if len(self.steps_values) > 0 else None

            self._update_steps(new_selection)

        def stepsPause(self):
            # add pause
            self._addStep('pause', 'Pause', None)

        def stepsScript(self):
            # add script
            file = self.values['stepsScript']
            self._addStep('script', f'Run "{os.path.basename(file)}"', file)

        def stepsBitstream(self):
            # add bistream
            file = self.values['stepsBitstream']
            self._addStep('bitstream', f'Program "{os.path.basename(file)}"', file)
            if VIVADO_BITSTREAM_LOAD:
                vivado.prepare(wait_ready=False)

        def _addStep(self, *step):
            selection = self.get_steps_selection()
            if selection is None:
                # if nothing is selected, add at the end
                selection = len(self.steps_values)
            else:
                # if something is selected, add below it
                # adding above is the logical choice (allows adding as first)
                # but adding below just feels more natural (allows adding sequences)
                selection += 1
            self.steps_values.insert(selection, step)
            self._update_steps(selection)

        def _update_steps(self, selection=-1):
            # sets the steps and selection values
            if selection is not None and selection < 0: selection += len(self.steps_values)
            self.window['steps'](values=[x[1] for x in self.steps_values] + [""], set_to_index=selection, scroll_to_index=selection)

    ui = CustomUI()

    # loop
    while ui.is_shown():
        # update
        fpgas.update()
        ui.update(fpgas)

        # tick
        ui.tick()

    vivado.close()
    print("Bye!")


@run_as_admin
def main_admin():
    try:
        main()
    except Exception as e:
        print("An exception occurred:")
        print(e)
        input("Press enter to exit")


if __name__ == '__main__':
    if 'no_admin' in os.environ:
        main()
    else:
        main_admin()
