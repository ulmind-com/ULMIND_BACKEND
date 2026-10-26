from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import Response
from typing import List
from bson import ObjectId
from xml.sax.saxutils import escape as xml_escape
from datetime import datetime, timezone
from email.utils import format_datetime
import logging

from app.db.database import get_db
from app.core.datetime_utils import get_now
from app.schemas.website_content import (
    WebsiteStatCreate, WebsiteStatUpdate, WebsiteStatResponse,
    TestimonialCreate, TestimonialUpdate, TestimonialResponse,
    PortfolioProjectCreate, PortfolioProjectUpdate, PortfolioProjectResponse,
    FestiveBannerBase, FestiveBannerUpdate, FestiveBannerResponse,
    BlogPostCreate, BlogPostUpdate, BlogPostResponse,
    ImageInfo
)
from app.api.deps import get_current_active_admin
from app.core.cloudinary import upload_image, delete_image, GENERAL_FOLDER

router = APIRouter()
logger = logging.getLogger(__name__)

STATS_COLLECTION = "website_stats"
TESTIMONIALS_COLLECTION = "testimonials"
PROJECTS_COLLECTION = "portfolio_projects"
FESTIVE_COLLECTION = "festive_banner"
FESTIVE_KEY = "singleton"
BLOGS_COLLECTION = "blogs"

def _parse_id(id: str) -> ObjectId:
    try:
        return ObjectId(id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid ID format")

# ══════════════════════════════════════════════════════════════════════════════
#  IMAGE UPLOAD
# ══════════════════════════════════════════════════════════════════════════════

@router.post("/upload-image", response_model=ImageInfo)
async def upload_content_image(
    image: UploadFile = File(...),
    _admin=Depends(get_current_active_admin)
):
    """Upload an image for CMS content."""
    file_bytes = await image.read()
    image_info = await upload_image(file_bytes, image.filename, folder=GENERAL_FOLDER)
    return image_info


# ══════════════════════════════════════════════════════════════════════════════
#  WEBSITE STATS
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/stats", response_model=List[WebsiteStatResponse])
async def list_stats(db=Depends(get_db)):
    """Get all website stats sorted by order."""
    stats = await db[STATS_COLLECTION].find({}).sort("order", 1).to_list(length=100)
    return stats

@router.post("/stats", response_model=WebsiteStatResponse, status_code=201)
async def create_stat(
    stat_in: WebsiteStatCreate,
    db=Depends(get_db),
    _admin=Depends(get_current_active_admin)
):
    """Create a new website stat."""
    now = get_now()
    doc = stat_in.model_dump()
    doc["created_at"] = now
    doc["updated_at"] = now
    
    result = await db[STATS_COLLECTION].insert_one(doc)
    created = await db[STATS_COLLECTION].find_one({"_id": result.inserted_id})
    return created

@router.put("/stats/{id}", response_model=WebsiteStatResponse)
async def update_stat(
    id: str,
    stat_in: WebsiteStatUpdate,
    db=Depends(get_db),
    _admin=Depends(get_current_active_admin)
):
    """Update a website stat."""
    update_data = stat_in.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields provided for update")
        
    update_data["updated_at"] = get_now()
    
    result = await db[STATS_COLLECTION].find_one_and_update(
        {"_id": _parse_id(id)},
        {"$set": update_data},
        return_document=True
    )
    if not result:
        raise HTTPException(status_code=404, detail="Stat not found")
    return result

@router.delete("/stats/{id}")
async def delete_stat(
    id: str,
    db=Depends(get_db),
    _admin=Depends(get_current_active_admin)
):
    """Delete a website stat."""
    result = await db[STATS_COLLECTION].delete_one({"_id": _parse_id(id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Stat not found")
    return {"status": "success"}

# ══════════════════════════════════════════════════════════════════════════════
#  TESTIMONIALS (REVIEWS)
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/testimonials", response_model=List[TestimonialResponse])
async def list_testimonials(db=Depends(get_db)):
    """Get all testimonials sorted by order."""
    items = await db[TESTIMONIALS_COLLECTION].find({}).sort("order", 1).to_list(length=100)
    return items

@router.post("/testimonials", response_model=TestimonialResponse, status_code=201)
async def create_testimonial(
    item_in: TestimonialCreate,
    db=Depends(get_db),
    _admin=Depends(get_current_active_admin)
):
    now = get_now()
    doc = item_in.model_dump()
    doc["created_at"] = now
    doc["updated_at"] = now
    
    result = await db[TESTIMONIALS_COLLECTION].insert_one(doc)
    created = await db[TESTIMONIALS_COLLECTION].find_one({"_id": result.inserted_id})
    return created

@router.put("/testimonials/{id}", response_model=TestimonialResponse)
async def update_testimonial(
    id: str,
    item_in: TestimonialUpdate,
    db=Depends(get_db),
    _admin=Depends(get_current_active_admin)
):
    update_data = item_in.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields provided for update")
        
    update_data["updated_at"] = get_now()
    
    result = await db[TESTIMONIALS_COLLECTION].find_one_and_update(
        {"_id": _parse_id(id)},
        {"$set": update_data},
        return_document=True
    )
    if not result:
        raise HTTPException(status_code=404, detail="Testimonial not found")
    return result

@router.delete("/testimonials/{id}")
async def delete_testimonial(
    id: str,
    db=Depends(get_db),
    _admin=Depends(get_current_active_admin)
):
    obj_id = _parse_id(id)
    existing = await db[TESTIMONIALS_COLLECTION].find_one({"_id": obj_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Testimonial not found")
        
    if existing.get("img") and existing["img"].get("public_id"):
        await delete_image(existing["img"]["public_id"])
        
    await db[TESTIMONIALS_COLLECTION].delete_one({"_id": obj_id})
    return {"status": "success"}

# ══════════════════════════════════════════════════════════════════════════════
#  PORTFOLIO PROJECTS
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/projects", response_model=List[PortfolioProjectResponse])
async def list_projects(db=Depends(get_db)):
    """Get all portfolio projects sorted by order."""
    items = await db[PROJECTS_COLLECTION].find({}).sort("order", 1).to_list(length=100)
    return items

@router.post("/projects", response_model=PortfolioProjectResponse, status_code=201)
async def create_project(
    item_in: PortfolioProjectCreate,
    db=Depends(get_db),
    _admin=Depends(get_current_active_admin)
):
    now = get_now()
    doc = item_in.model_dump()
    doc["created_at"] = now
    doc["updated_at"] = now
    
    result = await db[PROJECTS_COLLECTION].insert_one(doc)
    created = await db[PROJECTS_COLLECTION].find_one({"_id": result.inserted_id})
    return created

@router.put("/projects/{id}", response_model=PortfolioProjectResponse)
async def update_project(
    id: str,
    item_in: PortfolioProjectUpdate,
    db=Depends(get_db),
    _admin=Depends(get_current_active_admin)
):
    update_data = item_in.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields provided for update")
        
    update_data["updated_at"] = get_now()
    
    result = await db[PROJECTS_COLLECTION].find_one_and_update(
        {"_id": _parse_id(id)},
        {"$set": update_data},
        return_document=True
    )
    if not result:
        raise HTTPException(status_code=404, detail="Project not found")
    return result

@router.delete("/projects/{id}")
async def delete_project(
    id: str,
    db=Depends(get_db),
    _admin=Depends(get_current_active_admin)
):
    obj_id = _parse_id(id)
    existing = await db[PROJECTS_COLLECTION].find_one({"_id": obj_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Project not found")
        
    if existing.get("image") and existing["image"].get("public_id"):
        await delete_image(existing["image"]["public_id"])

    await db[PROJECTS_COLLECTION].delete_one({"_id": obj_id})
    return {"status": "success"}


# ══════════════════════════════════════════════════════════════════════════════
#  FESTIVE BANNER (singleton hero decoration config)
# ══════════════════════════════════════════════════════════════════════════════

def _as_utc(dt):
    """Return a tz-aware UTC datetime, treating naive values as UTC."""
    if dt is None:
        return None
    from datetime import timezone
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)

def _compute_active(cfg: dict) -> bool:
    if not cfg.get("enabled"):
        return False
    now = _as_utc(get_now())
    start = _as_utc(cfg.get("startAt"))
    end = _as_utc(cfg.get("endAt"))
    if start and now < start:
        return False
    if end and now > end:
        return False
    return True

@router.get("/festive-banner", response_model=FestiveBannerResponse)
async def get_festive_banner(db=Depends(get_db)):
    """Public: current festive-banner config plus a server-computed `active` flag."""
    cfg = await db[FESTIVE_COLLECTION].find_one({"key": FESTIVE_KEY})
    base = FestiveBannerBase().model_dump()  # sensible defaults
    if cfg:
        base.update({k: cfg[k] for k in base.keys() if k in cfg})
    return {**base, "active": _compute_active(base)}

@router.put("/festive-banner", response_model=FestiveBannerResponse)
async def update_festive_banner(
    cfg_in: FestiveBannerUpdate,
    db=Depends(get_db),
    _admin=Depends(get_current_active_admin)
):
    """Admin: upsert the singleton festive-banner config."""
    update_data = cfg_in.model_dump(exclude_unset=True)
    update_data["updated_at"] = get_now()
    await db[FESTIVE_COLLECTION].update_one(
        {"key": FESTIVE_KEY},
        {"$set": update_data, "$setOnInsert": {"key": FESTIVE_KEY}},
        upsert=True,
    )
    cfg = await db[FESTIVE_COLLECTION].find_one({"key": FESTIVE_KEY})
    base = FestiveBannerBase().model_dump()
    base.update({k: cfg[k] for k in base.keys() if k in cfg})
    return {**base, "active": _compute_active(base)}


# ══════════════════════════════════════════════════════════════════════════════
#  BLOG POSTS
# ══════════════════════════════════════════════════════════════════════════════

import re

def _slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text)
    return text.strip("-")

@router.get("/blogs", response_model=List[BlogPostResponse])
async def list_blogs(
    category: str = None,
    service: str = None,
    tag: str = None,
    search: str = None,
    limit: int = 50,
    skip: int = 0,
    db=Depends(get_db)
):
    """Public: list published blogs with optional filtering & search."""
    query: dict = {"published": True}
    if category and category != "All" and category != "All Industries":
        query["category"] = category
    if service and service != "All" and service != "All Services":
        query["service"] = service
    if tag:
        query["tags"] = {"$in": [tag]}
    if search and search.strip():
        s = search.strip()
        query["$or"] = [
            {"title": {"$regex": s, "$options": "i"}},
            {"excerpt": {"$regex": s, "$options": "i"}},
            {"category": {"$regex": s, "$options": "i"}},
            {"tags": {"$elemMatch": {"$regex": s, "$options": "i"}}}
        ]
    items = await db[BLOGS_COLLECTION].find(query).sort([("order", 1), ("createdAt", -1)]).skip(skip).limit(limit).to_list(length=limit)
    return items

@router.get("/blogs/admin/all", response_model=List[BlogPostResponse])
async def list_all_blogs_admin(
    db=Depends(get_db),
    _admin=Depends(get_current_active_admin)
):
    """Admin: list all blogs (including unpublished drafts)."""
    items = await db[BLOGS_COLLECTION].find({}).sort([("order", 1), ("createdAt", -1)]).to_list(length=200)
    return items


# ══════════════════════════════════════════════════════════════════════════════
#  RSS FEED
# ══════════════════════════════════════════════════════════════════════════════

SITE_URL = "https://www.ulmind.com"

def _rfc822(dt) -> str:
    """Convert a datetime or ISO string to RFC 822 for RSS <pubDate>."""
    if isinstance(dt, str):
        try:
            dt = datetime.fromisoformat(dt.replace("Z", "+00:00"))
        except Exception:
            dt = datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return format_datetime(dt, usegmt=True)

def _strip_md(text: str, max_len: int = 500) -> str:
    """Rough markdown-to-plain-text for RSS descriptions."""
    import re as _re
    text = _re.sub(r"!\[.*?\]\(.*?\)", "", text)       # images
    text = _re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", text)  # links
    text = _re.sub(r"[#*>`_~\-]", "", text)             # formatting chars
    text = _re.sub(r"\n{2,}", "\n", text).strip()
    if len(text) > max_len:
        text = text[:max_len].rsplit(" ", 1)[0] + "…"
    return text

def _cdata(text: str) -> str:
    """Safely wrap text in CDATA, replacing nested ]]> sequences."""
    safe = str(text or "").replace("]]>", "]]]]><![CDATA[>")
    return f"<![CDATA[{safe}]]>"

@router.get("/blogs/rss.xml", response_class=Response)
@router.get("/rss.xml", response_class=Response)
async def blogs_rss_feed(db=Depends(get_db)):
    """Public: RSS 2.0 feed of published blog posts for LinkedIn / RSS readers."""
    blogs = await (
        db[BLOGS_COLLECTION]
        .find({"published": True})
        .sort([("createdAt", -1)])
        .limit(50)
        .to_list(length=50)
    )

    items_xml = []
    for b in blogs:
        slug = b.get("slug", "")
        title = xml_escape(b.get("title", ""))
        link = f"{SITE_URL}/blogs/{slug}"
        desc = b.get("excerpt") or _strip_md(b.get("content", ""))
        raw_author = b.get("author", "ULMIND")
        pub_date = _rfc822(b.get("createdAt") or b.get("created_at", ""))
        category = b.get("category", "Technology")
        cover = b.get("coverImage", {}).get("url", "")

        mime_type = "image/jpeg"
        if cover.lower().endswith(".png"):
            mime_type = "image/png"
        elif cover.lower().endswith(".webp"):
            mime_type = "image/webp"

        media_blocks = []
        if cover:
            safe_cover = xml_escape(cover)
            media_blocks.append(f'<enclosure url="{safe_cover}" type="{mime_type}" length="102400"/>')
            media_blocks.append(f'<media:content url="{safe_cover}" medium="image" type="{mime_type}"/>')
            media_blocks.append(f'<media:thumbnail url="{safe_cover}"/>')

        media_xml = ("\n      " + "\n      ".join(media_blocks)) if media_blocks else ""

        items_xml.append(f"""    <item>
      <title>{title}</title>
      <link>{link}</link>
      <guid isPermaLink="true">{link}</guid>
      <pubDate>{pub_date}</pubDate>
      <dc:creator>{_cdata(raw_author)}</dc:creator>
      <author>contact@ulmind.com ({xml_escape(raw_author)})</author>
      <category>{_cdata(category)}</category>
      <description>{_cdata(desc)}</description>
      <content:encoded>{_cdata(f"<p>{desc}</p>")}</content:encoded>{media_xml}
    </item>""")

    channel_items = "\n".join(items_xml)
    now_rfc = _rfc822(datetime.now(timezone.utc))

    rss_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" 
  xmlns:content="http://purl.org/rss/1.0/modules/content/"
  xmlns:dc="http://purl.org/dc/elements/1.1/"
  xmlns:atom="http://www.w3.org/2005/Atom"
  xmlns:media="http://search.yahoo.com/mrss/">
  <channel>
    <title>ULMIND — Company Blog</title>
    <link>{SITE_URL}/blogs</link>
    <description>Engineering insights, product updates and industry perspectives from the ULMIND team.</description>
    <language>en-us</language>
    <lastBuildDate>{now_rfc}</lastBuildDate>
    <atom:link href="{SITE_URL}/rss.xml" rel="self" type="application/rss+xml"/>
    <image>
      <url>{SITE_URL}/logo.png</url>
      <title>ULMIND</title>
      <link>{SITE_URL}</link>
    </image>
{channel_items}
  </channel>
</rss>"""

    return Response(
        content=rss_xml,
        media_type="application/rss+xml; charset=utf-8",
        headers={"Cache-Control": "public, max-age=1800"},
    )


@router.get("/blogs/{slug_or_id}", response_model=BlogPostResponse)
async def get_blog_detail(slug_or_id: str, db=Depends(get_db)):
    """Public: get single blog by slug or ID, increments views."""
    query = {"slug": slug_or_id}
    try:
        obj_id = ObjectId(slug_or_id)
        query = {"$or": [{"slug": slug_or_id}, {"_id": obj_id}]}
    except Exception:
        pass

    blog = await db[BLOGS_COLLECTION].find_one_and_update(
        query,
        {"$inc": {"views": 1}},
        return_document=True
    )
    if not blog:
        raise HTTPException(status_code=404, detail="Blog post not found")
    return blog

@router.post("/blogs", response_model=BlogPostResponse, status_code=201)
async def create_blog(
    blog_in: BlogPostCreate,
    db=Depends(get_db),
    _admin=Depends(get_current_active_admin)
):
    """Admin: create a new blog post."""
    now = get_now()
    doc = blog_in.model_dump()
    if not doc.get("slug"):
        doc["slug"] = _slugify(doc["title"])
    else:
        doc["slug"] = _slugify(doc["slug"])

    # Ensure unique slug
    existing = await db[BLOGS_COLLECTION].find_one({"slug": doc["slug"]})
    if existing:
        doc["slug"] = f"{doc['slug']}-{int(now.timestamp())}"

    doc["created_at"] = now
    doc["updated_at"] = now
    if "views" not in doc:
        doc["views"] = 0

    result = await db[BLOGS_COLLECTION].insert_one(doc)
    created = await db[BLOGS_COLLECTION].find_one({"_id": result.inserted_id})
    return created

@router.put("/blogs/{id}", response_model=BlogPostResponse)
async def update_blog(
    id: str,
    blog_in: BlogPostUpdate,
    db=Depends(get_db),
    _admin=Depends(get_current_active_admin)
):
    """Admin: update a blog post."""
    update_data = blog_in.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields provided for update")

    if "slug" in update_data and update_data["slug"]:
        update_data["slug"] = _slugify(update_data["slug"])

    update_data["updated_at"] = get_now()

    result = await db[BLOGS_COLLECTION].find_one_and_update(
        {"_id": _parse_id(id)},
        {"$set": update_data},
        return_document=True
    )
    if not result:
        raise HTTPException(status_code=404, detail="Blog not found")
    return result

@router.delete("/blogs/{id}")
async def delete_blog(
    id: str,
    db=Depends(get_db),
    _admin=Depends(get_current_active_admin)
):
    """Admin: delete a blog post."""
    obj_id = _parse_id(id)
    existing = await db[BLOGS_COLLECTION].find_one({"_id": obj_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Blog not found")

    if existing.get("coverImage") and existing["coverImage"].get("public_id"):
        try:
            await delete_image(existing["coverImage"]["public_id"])
        except Exception as e:
            logger.warning(f"Failed to delete blog cover image: {e}")

    await db[BLOGS_COLLECTION].delete_one({"_id": obj_id})
    return {"status": "success", "message": "Blog deleted successfully"}
