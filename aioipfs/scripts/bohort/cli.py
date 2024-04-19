from ptpython.prompt_style import PromptStyle
from ptpython.layout import CompletionVisualisation
from prompt_toolkit import print_formatted_text, HTML
from omegaconf import DictConfig


def configure(config: DictConfig, repl) -> None:
    class CustomPrompt(PromptStyle):
        def in_prompt(self):
            return HTML("<{ipcolor}>bohort [{idx}]</{ipcolor}>: ".format(
                ipcolor=config.repl.input_prompt_color,
                idx=repl.current_statement_index
            ))

        def in2_prompt(self, width):
            return "...: ".rjust(width)

        def out_prompt(self):
            return HTML("<{opcolor}>Result[{idx}]</{opcolor}>: ".format(
                opcolor=config.repl.output_prompt_color,
                idx=repl.current_statement_index
            ))

    repl.all_prompt_styles["custom"] = CustomPrompt()
    repl.cursor_shape_config = config.repl.cursor_shape
    repl.insert_blank_line_after_output = True
    repl.prompt_style = "custom"
    repl.show_signature = config.repl.show_signature
    repl.enable_history_search = config.repl.enable_history_search
    repl.enable_auto_suggest = config.repl.enable_auto_suggest
    repl.title = 'bohort'
    repl.confirm_exit = config.repl.confirm_exit
    repl.vi_keep_last_used_mode = True
    repl.completion_menu_scroll_offset = 0
    repl.complete_while_typing = config.repl.complete_while_typing
    repl.enable_input_validation = True

    cvisual = config.repl.get('completion_visualisation')

    if cvisual in ['TOOLBAR', 'POP_UP', 'MULTI_COLUMN']:
        repl.completion_visualisation = getattr(CompletionVisualisation,
                                                cvisual)

    repl.use_code_colorscheme(config.repl.color_scheme)


def pf_text(text: str, color: str = 'ansiyellow') -> None:
    print_formatted_text(HTML(f'<{color}>{text}</{color}>'))
