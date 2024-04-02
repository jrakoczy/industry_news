def header(title: str, level: int = 1) -> str:
    return f"{'#' * level} {title}"


def link(text: str, url: str) -> str:
    return f"[{text}]({url})"


def collapsible_section(details: str, title: str) -> str:
    return (
        "<details>\n"
        f"    <summary>{title}</summary>\n"
        f"    {details}\n"
        "</details>"
    )
