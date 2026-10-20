from src.geo import ancestors, is_inside_cali, locate


def ids(text):
    return {p["id"] for p in locate(text)}


def test_unambiguous_barrios_corregimientos_and_comunas_are_found():
    assert "barrio:2003" in ids("Inundaciones en Siloé")
    assert ids("Huecos en la vía a Pance y en La Buitrera") >= {"corregimiento:53", "corregimiento:54"}
    assert ids("Las comunas 13, 14 y 15 sin agua") >= {"comuna:13", "comuna:14", "comuna:15"}
    assert "comuna:18" in ids("alternancia en la comuna dieciocho")


def test_ambiguous_names_need_a_barrio_trigger_and_to_be_about_cali():
    assert ids("Petro habló de la paz total") == set()
    assert ids("Simón Bolívar dijo") == set()
    assert "barrio:0802" in ids("Vecinos del barrio Simón Bolívar en Cali")
    assert ids("operación militar en la vereda La Esperanza") == set()  # puede ser de otro municipio


def test_trigger_word_picks_the_level_and_cities_win_over_homonym_barrios():
    assert "barrio:0214" in ids("Balacera en el barrio La Paz de Cali")
    assert "corregimiento:63" in ids("corregimiento La Paz, Cali")
    assert ids("Junior de Barranquilla") == {"municipio:08001"}  # no el barrio Los Parques - Barranquilla
    assert "municipio:11001" in ids("En Bogotá")


def test_distrito_de_aguablanca_is_its_four_comunas():
    assert ids("Obras en el Distrito de Aguablanca") == {"comuna:13", "comuna:14", "comuna:15", "comuna:21"}


def test_hierarchy_rolls_barrios_up_to_comuna_and_city():
    assert ancestors("barrio:0216") == ["comuna:02", "municipio:76001", "departamento:76"]
    assert is_inside_cali("barrio:0216") and not is_inside_cali("municipio:76001")
