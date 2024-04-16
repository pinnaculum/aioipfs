from ptpython.prompt_style import PromptStyle
from ptpython.layout import CompletionVisualisation
from prompt_toolkit.formatted_text import HTML


def configure(repl):
    class CustomPrompt(PromptStyle):
        def in_prompt(self):
            return HTML("<ansigreen>bohort [%s]</ansigreen>: ") % (
                repl.current_statement_index
            )

        def in2_prompt(self, width):
            return "...: ".rjust(width)

        def out_prompt(self):
            return HTML("<ansicyan>Result[%s]</ansicyan>: ") % (
                repl.current_statement_index
            )

    repl.all_prompt_styles["custom"] = CustomPrompt()
    repl.cursor_shape_config = "Blink block"
    repl.insert_blank_line_after_output = True
    repl.use_code_colorscheme('native')
    repl.prompt_style = "custom"
    repl.show_signature = True
    repl.enable_history_search = True
    repl.enable_auto_suggest = True
    repl.title = 'bohort'
    repl.confirm_exit = False
    repl.vi_keep_last_used_mode = True
    repl.completion_visualisation = CompletionVisualisation.POP_UP
    repl.completion_menu_scroll_offset = 0
    repl.complete_while_typing = False
