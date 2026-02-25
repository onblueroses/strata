use console::Style;

pub fn success(msg: &str) {
    let style = Style::new().green().bold();
    println!("{} {}", style.apply_to("✓"), msg);
}

pub fn warning(msg: &str) {
    let style = Style::new().yellow().bold();
    println!("{} {}", style.apply_to("⚠"), msg);
}

pub fn error(msg: &str) {
    let style = Style::new().red().bold();
    eprintln!("{} {}", style.apply_to("✗"), msg);
}

pub fn info(msg: &str) {
    let style = Style::new().cyan();
    println!("{} {}", style.apply_to("ℹ"), msg);
}

pub fn header(msg: &str) {
    let style = Style::new().bold().underlined();
    println!("\n{}", style.apply_to(msg));
}

#[expect(dead_code, reason = "utility function for future UI enhancements")]
pub fn dim(msg: &str) {
    let style = Style::new().dim();
    println!("  {}", style.apply_to(msg));
}

pub fn file_action(action: &str, path: &str) {
    let action_style = Style::new().green();
    let path_style = Style::new().dim();
    println!(
        "  {} {}",
        action_style.apply_to(action),
        path_style.apply_to(path)
    );
}
