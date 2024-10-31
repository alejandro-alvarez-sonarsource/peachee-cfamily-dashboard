function set_theme(theme) {
    document.documentElement.setAttribute('data-bs-theme', theme);
    localStorage.setItem('theme', theme);
}

set_theme(localStorage.getItem('theme') || 'light');
