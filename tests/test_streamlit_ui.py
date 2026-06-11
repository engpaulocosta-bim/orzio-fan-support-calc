from streamlit.testing.v1 import AppTest


def test_fan_weight_edit_keeps_page_rendering():
    app = AppTest.from_file("app.py", default_timeout=10)
    app.run()

    assert not app.exception
    weight_inputs = [field for field in app.number_input if "Peso vazio" in field.label]
    assert weight_inputs

    weight_inputs[0].set_value(155.0)
    app.run()

    assert not app.exception
    # A página tem de continuar a desenhar os widgets após o rerun, não ficar vazia.
    assert [field for field in app.number_input if "Peso vazio" in field.label]
    assert len(app.selectbox) > 0


def test_rerun_keeps_rendering_widgets():
    """Regressão: o Streamlit re-executa app.py a cada interação. Se a UI for
    apenas importada (e não executada) o corpo não corre nos reruns e a página
    fica em branco. Garantir que os widgets continuam a ser desenhados."""
    app = AppTest.from_file("app.py", default_timeout=10)
    app.run()
    assert not app.exception
    n_widgets = len(app.selectbox)
    assert n_widgets > 0

    # Vários reruns sem interação não devem esvaziar a página.
    for _ in range(3):
        app.run()
        assert not app.exception
        assert len(app.selectbox) == n_widgets


def _set_engineer(app):
    """Preenche o engenheiro responsável (gate de exportação — Fase 3)."""
    eng = [f for f in app.text_input if "Engenheiro responsável" in f.label]
    if eng:
        eng[0].set_value("Eng. Teste")


def test_results_persist_across_rerun_for_downloads():
    """Regressão: os botões de download disparam um rerun com calc_btn=False.
    Se os resultados forem renderizados apenas dentro de `if calc_btn:`, esse
    rerun apaga tudo e volta ao ecrã inicial — o download nunca dispara.
    O resultado tem de persistir em session_state."""
    app = AppTest.from_file("app.py", default_timeout=60)
    app.run()

    _set_engineer(app)
    calc = [b for b in app.button if "Calcular" in b.label]
    assert calc
    calc[0].click()
    app.run()
    assert not app.exception
    assert len(app.metric) > 0
    assert len(app.get("download_button")) == 3

    # Um rerun sem clicar Calcular (equivale a clicar num botão de download)
    # não pode esvaziar os resultados nem os botões de download.
    app.run()
    assert not app.exception
    assert len(app.metric) > 0
    assert len(app.get("download_button")) == 3


def test_export_gated_until_engineer_filled():
    """Sem engenheiro responsável, os botões de download não aparecem (F3.5)."""
    app = AppTest.from_file("app.py", default_timeout=60)
    app.run()
    calc = [b for b in app.button if "Calcular" in b.label][0]
    calc.click()
    app.run()
    assert not app.exception
    assert len(app.metric) > 0  # resultados aparecem…
    assert len(app.get("download_button")) == 0  # …mas o export está bloqueado


def test_verify_mode_available_in_ui():
    """O modo VERIFY tem de estar exposto na UI (auditoria M-03)."""
    app = AppTest.from_file("app.py", default_timeout=60)
    app.run()
    modes = [r for r in app.radio if "Modo de cálculo" in r.label]
    assert modes
    assert "Verificar perfil existente" in modes[0].options


def test_calculation_lists_passing_sections_for_user_choice():
    """Depois de calcular, a UI deve listar perfis aprovados para escolha."""
    app = AppTest.from_file("app.py", default_timeout=60)
    app.run()

    calc = [b for b in app.button if "Calcular" in b.label][0]
    calc.click()
    app.run()

    assert not app.exception
    assert len(app.metric) > 0
    profile_selectors = [
        s for s in app.selectbox if s.label == "Perfil ativo para resultados e documentos"
    ]
    assert profile_selectors
    assert len(profile_selectors[0].options) >= 1
