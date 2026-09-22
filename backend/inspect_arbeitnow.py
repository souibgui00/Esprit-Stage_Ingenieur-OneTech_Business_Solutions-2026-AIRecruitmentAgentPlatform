"""
Script to inspect the actual DOM structure of the Arbeitnow job page
to understand the apply link structure.
"""
import asyncio
from playwright.async_api import async_playwright

async def inspect_arbeitnow():
    url = "https://www.arbeitnow.com/jobs/companies/autarcenergy/internship-go-to-market-engineering-ai-automation-berlin-236643"
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        
        print(f"Navigating to: {url}")
        await page.goto(url, wait_until="networkidle")
        
        print("\n=== PAGE INFO ===")
        print(f"Title: {page.title()}")
        print(f"URL: {page.url}")
        
        print("\n=== ALL LINKS ===")
        links = await page.locator('a').all()
        print(f"Total links found: {len(links)}")
        
        for i, link in enumerate(links[:20]):  # First 20 links
            try:
                text = await link.inner_text()
                href = await link.get_attribute('href')
                class_attr = await link.get_attribute('class')
                print(f"{i+1}. Text: '{text.strip()}'")
                print(f"   Href: {href}")
                print(f"   Class: {class_attr}")
                print()
            except Exception as e:
                print(f"{i+1}. Error: {e}")
        
        print("\n=== LINKS CONTAINING 'APPLY' (case-insensitive) ===")
        apply_links = page.locator('a:has-text("Apply"), a:has-text("apply"), a:has-text("APPLY")')
        apply_count = await apply_links.count()
        print(f"Found {apply_count} links with 'Apply'")
        
        for i in range(min(apply_count, 10)):
            link = apply_links.nth(i)
            try:
                text = await link.inner_text()
                href = await link.get_attribute('href')
                class_attr = await link.get_attribute('class')
                print(f"{i+1}. Text: '{text.strip()}'")
                print(f"   Href: {href}")
                print(f"   Class: {class_attr}")
                print()
            except Exception as e:
                print(f"{i+1}. Error: {e}")
        
        print("\n=== LINKS WITH EXTERNAL HREFS ===")
        external_links = []
        for i, link in enumerate(links):
            try:
                href = await link.get_attribute('href')
                if href and ('arbeitnow.com' not in href.lower()):
                    text = await link.inner_text()
                    class_attr = await link.get_attribute('class')
                    external_links.append({
                        'text': text.strip(),
                        'href': href,
                        'class': class_attr
                    })
            except:
                pass
        
        print(f"Found {len(external_links)} external links")
        for i, link in enumerate(external_links[:15]):
            print(f"{i+1}. Text: '{link['text']}'")
            print(f"   Href: {link['href']}")
            print(f"   Class: {link['class']}")
            print()
        
        print("\n=== BUTTONS ===")
        buttons = await page.locator('button').all()
        print(f"Total buttons found: {len(buttons)}")
        
        for i, button in enumerate(buttons[:10]):
            try:
                text = await button.inner_text()
                class_attr = await button.get_attribute('class')
                type_attr = await button.get_attribute('type')
                print(f"{i+1}. Text: '{text.strip()}'")
                print(f"   Class: {class_attr}")
                print(f"   Type: {type_attr}")
                print()
            except Exception as e:
                print(f"{i+1}. Error: {e}")
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(inspect_arbeitnow())