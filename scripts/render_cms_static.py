#!/usr/bin/env python3
import csv
import datetime as dt
import html
import re
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
BLOG_CSV = BASE_DIR / "Tania Jones - Blog Posts.csv"
DOWNLOADS_CSV = BASE_DIR / "Tania Jones - Participation Downloads.csv"
BLOG_TEMPLATE = BASE_DIR / "detail_blog.html"
DOWNLOAD_TEMPLATE = BASE_DIR / "templates" / "participation-download.html"

EXTERNAL_LINK_OVERRIDES = {
    "about the research": "https://vimeo.com/807135567",
    "researcher at school quick info": "https://vimeo.com/791531490",
    "previous research exploring volunteers in school": "https://communityresearch.org.nz/research/volunteers-enriching-education-in-aotearoa-new-zealand/",
    "previous research exploring volunteers at school": "https://communityresearch.org.nz/research/volunteers-enriching-education-in-aotearoa-new-zealand/",
}

DOWNLOAD_FILE_OVERRIDES = {
    "consent-to-interview-staff": "concenttointerviewstaff.pdf",
    "consent-to-interview-parents-caregivers": "concenttointerviewparents.pdf",
    "information-sheet-for-staff": "informationsheetforstaff.pdf",
    "information-sheet-for-parents": "informationsheetforparents.pdf",
    "researcher-at-school": "researcheratschool.pdf",
    "researcher-at-school-poster": "researcheratschoolposter.pdf",
}


def slugify(value):
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-") or "item"


def parse_date(value):
    if not value:
        return dt.datetime.min
    try:
        main = value.split(" GMT")[0]
        return dt.datetime.strptime(main, "%a %b %d %Y %H:%M:%S")
    except Exception:
        return dt.datetime.min


def replace_first(text, old, new):
    idx = text.find(old)
    if idx == -1:
        return text
    return text[:idx] + new + text[idx + len(old) :]


def replace_meta(text, attr, value, is_name=False):
    if is_name:
        pattern = rf'<meta content="[^"]*" name="{re.escape(attr)}">'
        replacement = f'<meta content="{value}" name="{attr}">'
    else:
        pattern = rf'<meta content="[^"]*" property="{re.escape(attr)}">'
        replacement = f'<meta content="{value}" property="{attr}">'
    return re.sub(pattern, replacement, text, count=1)


def replace_dyn_image(text, src, alt):
    def repl(match):
        tag = match.group(0)
        tag = re.sub(r'src="[^"]*"', f'src="{src}"', tag, count=1)
        tag = re.sub(r'alt="[^"]*"', f'alt="{alt}"', tag, count=1)
        return tag

    return re.sub(
        r'<img[^>]*class="[^"]*w-dyn-bind-empty[^"]*"[^>]*>',
        repl,
        text,
        count=1,
    )


def find_nth(text, needle, n):
    start = 0
    idx = -1
    for _ in range(n):
        idx = text.find(needle, start)
        if idx == -1:
            return -1
        start = idx + len(needle)
    return idx


def find_matching_div_end(text, start_idx):
    tag_re = re.compile(r"</?div\b", re.IGNORECASE)
    count = 0
    pos = start_idx
    while True:
        match = tag_re.search(text, pos)
        if not match:
            return -1
        if text[match.start() + 1] != "/":
            count += 1
        else:
            count -= 1
        pos = match.end()
        if count == 0:
            end = text.find(">", match.start())
            return end + 1


def replace_list_container(text, class_value, new_inner, occurrence=1):
    start_tag = f'<div role="list" class="{class_value}">'
    start_idx = find_nth(text, start_tag, occurrence)
    if start_idx == -1:
        raise ValueError(f"Could not find list container: {class_value}")
    start_tag_end = text.find(">", start_idx) + 1
    end_idx = find_matching_div_end(text, start_idx)
    if end_idx == -1:
        raise ValueError(f"Could not match list container end: {class_value}")
    close_start = text.rfind("</div", start_tag_end, end_idx)
    if close_start == -1:
        raise ValueError(f"Could not locate closing tag: {class_value}")
    return text[:start_tag_end] + "\n" + new_inner + "\n" + text[close_start:]


def strip_empty_states(text):
    pattern = re.compile(
        r'<div[^>]*class="[^"]*w-dyn-empty[^"]*"[^>]*>',
        re.IGNORECASE,
    )
    div_tag = re.compile(r"</?div\b", re.IGNORECASE)
    output = []
    pos = 0

    while True:
        match = pattern.search(text, pos)
        if not match:
            output.append(text[pos:])
            break
        start = match.start()
        output.append(text[pos:start])

        count = 0
        scan = start
        while True:
            next_tag = div_tag.search(text, scan)
            if not next_tag:
                pos = start
                break
            if text[next_tag.start() + 1] != "/":
                count += 1
            else:
                count -= 1
            scan = next_tag.end()
            if count == 0:
                pos = text.find(">", next_tag.start()) + 1
                break
    return "".join(output)


def read_csv(path):
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def build_blog_posts():
    posts = []
    for row in read_csv(BLOG_CSV):
        if row.get("Archived", "").lower() == "true":
            continue
        if row.get("Draft", "").lower() == "true":
            continue
        title = row.get("Blog Post - Title", "").strip()
        slug = row.get("Blog Post - Link", "").strip() or slugify(title)
        summary = (row.get("Blog Post - Summary") or "").strip()
        excerpt = (row.get("Blog Post - Excerpt") or "").strip()
        description = summary or excerpt
        image = (row.get("Blog Post - Featured Image") or "").strip()
        if not image:
            image = (row.get("Blog Post - Thumbnail") or "").strip()
        external = (row.get("External Media Link") or "").strip()
        published = parse_date(
            row.get("Published On") or row.get("Updated On") or row.get("Created On")
        )
        override = EXTERNAL_LINK_OVERRIDES.get(title.lower())
        link_url = override or f"updates-{slug}.html"
        link_external = bool(override)
        posts.append(
            {
                "title": title,
                "slug": slug,
                "summary": description,
                "image": image,
                "external": external,
                "published": published,
                "link_url": link_url,
                "link_external": link_external,
            }
        )
    return posts


def build_downloads():
    downloads = []
    for row in read_csv(DOWNLOADS_CSV):
        if row.get("Archived", "").lower() == "true":
            continue
        if row.get("Draft", "").lower() == "true":
            continue
        title = row.get("Name", "").strip()
        slug = row.get("Slug", "").strip() or slugify(title)
        description = (row.get("Download description") or "").strip()
        url = (row.get("Downloadable content") or "").strip()
        download_attr = ""
        file_override = DOWNLOAD_FILE_OVERRIDES.get(slug)
        if file_override:
            local_path = BASE_DIR / "downloads" / file_override
            if local_path.exists():
                url = f"downloads/{file_override}"
                download_attr = "download"
        downloads.append(
            {
                "title": title,
                "slug": slug,
                "description": description,
                "url": url,
                "download_attr": download_attr,
            }
        )
    return downloads


def render_blog_pages(posts):
    template = BLOG_TEMPLATE.read_text(encoding="utf-8")
    for post in posts:
        title = html.escape(post["title"])
        summary = html.escape(post["summary"])
        image = html.escape(post["image"])
        external = html.escape(post["external"])

        page = template
        page = page.replace("<title></title>", f"<title>{title} | Parent Volunteers</title>", 1)
        if summary:
            page = replace_meta(page, "description", summary, is_name=True)
            page = replace_meta(page, "og:description", summary)
            page = replace_meta(page, "twitter:description", summary)
        page = replace_meta(page, "og:title", title)
        page = replace_meta(page, "twitter:title", title)
        if image:
            page = replace_meta(page, "og:image", image)
            page = replace_meta(page, "twitter:image", image)

        page = replace_first(
            page,
            '<h1 class="w-dyn-bind-empty"></h1>',
            f'<h1 class="w-dyn-bind-empty">{title}</h1>',
        )
        page = replace_first(
            page,
            '<p class="mg-bottom-0 w-dyn-bind-empty"></p>',
            f'<p class="mg-bottom-0 w-dyn-bind-empty">{summary}</p>',
        )
        if image:
            page = replace_dyn_image(page, image, title)
        rich_parts = []
        if external:
            rich_parts.append(
                f'<p><a href="{external}" target="_blank" rel="noopener noreferrer">View resource</a></p>'
            )
        if not rich_parts and summary:
            rich_parts.append(f"<p>{summary}</p>")
        rich_html = "".join(rich_parts)
        page = replace_first(
            page,
            '<div class="rich-text w-dyn-bind-empty w-richtext"></div>',
            f'<div class="rich-text w-dyn-bind-empty w-richtext">{rich_html}</div>',
        )

        output_path = BASE_DIR / f"updates-{post['slug']}.html"
        output_path.write_text(page, encoding="utf-8")


def render_download_pages(downloads):
    template = DOWNLOAD_TEMPLATE.read_text(encoding="utf-8")
    for item in downloads:
        page = template
        page = page.replace("{{title}}", html.escape(item["title"]))
        page = page.replace("{{description}}", html.escape(item["description"]))
        page = page.replace("{{download_url}}", html.escape(item["url"]))
        page = page.replace("{{download_attr}}", item["download_attr"])
        output_path = BASE_DIR / f"participation-download-{item['slug']}.html"
        output_path.write_text(page, encoding="utf-8")


def update_get_involved(downloads):
    path = BASE_DIR / "get-involved.html"
    html_text = path.read_text(encoding="utf-8")
    items = []
    for item in downloads:
        title = html.escape(item["title"])
        description = html.escape(item["description"])
        url = item["url"]
        download_attr = f' {item["download_attr"]}' if item["download_attr"] else ""
        items.append(
            "\n".join(
                [
                    '<div role="listitem" class="w-dyn-item">',
                    f'  <a href="{url}" class="link-block w-inline-block"{download_attr}>',
                    '    <div class="card card-dark---square-bottom-left-corner icon-bottom">',
                    '      <div class="inner-container _188px">',
                    f'        <h3 class="display-4 color-neutral-100 mg-bottom-16px">{title}</h3>',
                    "      </div>",
                    f'      <p class="mg-bottom-40px">{description}</p>',
                    '      <div class="mg-top-auto"><img src="images/press-card-link-icon-consultflow-webflow-ecommerce-template.svg" loading="eager" alt="Press - Consultflow X Webflow Template"></div>',
                    "    </div>",
                    "  </a>",
                    "</div>",
                ]
            )
        )
    html_text = replace_list_container(
        html_text,
        "collection-list w-dyn-items",
        "\n".join(items),
        occurrence=1,
    )
    html_text = strip_empty_states(html_text)
    path.write_text(html_text, encoding="utf-8")


def update_updates(posts):
    path = BASE_DIR / "updates.html"
    html_text = path.read_text(encoding="utf-8")
    if "updates-featured-grid" not in html_text:
        html_text = html_text.replace(
            "grid-2-columns _1-col-tablet gap-row-80px",
            "grid-2-columns _1-col-tablet gap-row-80px updates-featured-grid",
            1,
        )
    sorted_posts = sorted(posts, key=lambda p: p["published"], reverse=True)

    featured = sorted_posts[:1]
    secondary = sorted_posts[1:3]
    all_posts = sorted_posts

    def featured_item(post):
        title = html.escape(post["title"])
        summary = html.escape(post["summary"])
        image = html.escape(post["image"])
        url = html.escape(post["link_url"])
        target = ' target="_blank" rel="noopener noreferrer"' if post["link_external"] else ""
        return "\n".join(
            [
                '<div role="listitem" class="w-dyn-item updates-featured-primary">',
                f'  <a href="{url}" class="blog-post-link-item w-inline-block"{target}>',
                f'    <div class="link---image-wrapper mg-bottom-24px"><img src="{image}" loading="eager" alt="{title}" class="link---image"></div>',
                f'    <h3 class="link-title-white---hover-secondary-6 heading-h2-size mg-bottom-16px">{title}</h3>',
                f'    <p class="color-neutral-200 mg-bottom-0">{summary}</p>',
                "  </a>",
                "</div>",
            ]
        )

    def secondary_item(post):
        title = html.escape(post["title"])
        image = html.escape(post["image"])
        url = html.escape(post["link_url"])
        target = ' target="_blank" rel="noopener noreferrer"' if post["link_external"] else ""
        return "\n".join(
            [
                '<div role="listitem" class="w-dyn-item">',
                f'  <a href="{url}" class="blog-post-link-item small-image-left w-inline-block"{target}>',
                f'    <div class="link---image-wrapper"><img src="{image}" loading="eager" alt="{title}" class="link---image"></div>',
                '    <div>',
                f'      <h3 class="link-title-white---hover-accent mg-bottom-0">{title}</h3>',
                "    </div>",
                "  </a>",
                "</div>",
            ]
        )

    def grid_item(post):
        title = html.escape(post["title"])
        summary = html.escape(post["summary"])
        image = html.escape(post["image"])
        url = html.escape(post["link_url"])
        target = ' target="_blank" rel="noopener noreferrer"' if post["link_external"] else ""
        return "\n".join(
            [
                '<div role="listitem" class="w-dyn-item">',
                f'  <a href="{url}" class="blog-post-link-item w-inline-block"{target}>',
                f'    <div class="link---image-wrapper mg-bottom-24px"><img src="{image}" loading="eager" alt="{title}" class="link---image"></div>',
                f'    <h3 class="link-title---hover-accent mg-bottom-10px">{title}</h3>',
                '    <div class="blog-post-details-container">',
                f'      <div class="text-200 medium color-neutral-700">{summary}</div>',
                '      <div class="line-rounded-icon link-icon-right font-size-32px">&#xe805;</div>',
                "    </div>",
                "  </a>",
                "</div>",
            ]
        )

    html_text = replace_list_container(
        html_text,
        "w-dyn-items",
        "\n".join(featured_item(post) for post in featured),
        occurrence=1,
    )
    html_text = replace_list_container(
        html_text,
        "grid-1-column gap-row-40px gap-row-24px-tablet w-dyn-items",
        "\n".join(secondary_item(post) for post in secondary),
        occurrence=1,
    )
    html_text = replace_list_container(
        html_text,
        "grid-3-columns gap-column-32px gap-row-64px w-dyn-items",
        "\n".join(grid_item(post) for post in all_posts),
        occurrence=1,
    )
    html_text = strip_empty_states(html_text)
    path.write_text(html_text, encoding="utf-8")


def main():
    posts = build_blog_posts()
    downloads = build_downloads()
    render_blog_pages(posts)
    render_download_pages(downloads)
    update_get_involved(downloads)
    update_updates(posts)
    print(f"Generated {len(posts)} blog pages and {len(downloads)} download pages.")


if __name__ == "__main__":
    main()
