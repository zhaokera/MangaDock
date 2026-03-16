# 漫画下载项目性能优化方案

## 当前性能瓶颈分析

### 1. 浏览器启动开销
- 每次下载都启动新的 Playwright 浏览器实例
- 启动时间约 2-3 秒
- 内存占用高

### 2. 等待时间过长
- 多处 `wait_for_timeout(3000)`、`wait_for_timeout(5000)` 等固定等待
- 实际页面加载可能只需要几百毫秒
- 总等待时间累积可达 10-20 秒

### 3. 并发限制
- 图片下载并发数限制为 5
- HTTP 连接未复用
- 串行页面解析

### 4. 重试机制开销
- 图片下载失败会重试 3 次
- 每次重试等待 0.5 秒
- 增加总下载时间

## 具体优化建议

### 1. 浏览器实例复用
```python
# 创建全局浏览器池
BROWSER_POOL = []
MAX_BROWSERS = 3

async def get_browser():
    if BROWSER_POOL:
        return BROWSER_POOL.pop()
    else:
        # 启动新浏览器
        playwright = await async_playwright().start()
        browser = await playwright.chromium.launch(
            headless=True,
            args=['--no-sandbox', '--disable-dev-shm-usage']
        )
        return browser, playwright

async def return_browser(browser, playwright):
    if len(BROWSER_POOL) < MAX_BROWSERS:
        BROWSER_POOL.append((browser, playwright))
    else:
        await browser.close()
        await playwright.stop()
```

### 2. 智能等待替代固定等待
```python
# 替换 wait_for_timeout 为智能等待
async def wait_for_images_loaded(page, timeout=10000):
    """等待图片加载完成"""
    try:
        # 等待图片容器出现
        await page.wait_for_selector('img[src*="hamreus"]', timeout=timeout)
        # 等待网络空闲
        await page.wait_for_load_state('networkidle', timeout=timeout)
    except:
        pass  # 超时则继续

# 在代码中替换：
# await self.page.wait_for_timeout(3000)
# 改为：
await wait_for_images_loaded(self.page, timeout=3000)
```

### 3. 增加并发数和连接复用
```python
# 增加并发数到 10
semaphore = asyncio.Semaphore(10)

# 使用 httpx 客户端池
class HttpClientPool:
    def __init__(self):
        self.clients = []
        self.lock = asyncio.Lock()
    
    async def get_client(self):
        async with self.lock:
            if self.clients:
                return self.clients.pop()
            else:
                return httpx.AsyncClient(timeout=30, follow_redirects=True)
    
    async def return_client(self, client):
        async with self.lock:
            if len(self.clients) < 5:
                self.clients.append(client)
            else:
                await client.aclose()

HTTP_CLIENT_POOL = HttpClientPool()
```

### 4. 优化重试策略
```python
# 减少重试次数，增加智能判断
async def download_image_optimized(self, url: str, filepath: Path, headers: Optional[dict] = None) -> bool:
    """优化的图片下载，减少不必要的重试"""
    try:
        client = await HTTP_CLIENT_POOL.get_client()
        response = await client.get(url, headers=headers)
        if response.status_code == 200 and len(response.content) > 100:  # 最小文件大小检查
            filepath.write_bytes(response.content)
            await HTTP_CLIENT_POOL.return_client(client)
            return True
        else:
            await HTTP_CLIENT_POOL.return_client(client)
            return False
    except Exception as e:
        # 只在特定错误时重试
        if "timeout" in str(e).lower() or "connection" in str(e).lower():
            await HTTP_CLIENT_POOL.return_client(client)
            return await self.download_image_optimized(url, filepath, headers)  # 仅重试一次
        else:
            await HTTP_CLIENT_POOL.return_client(client)
            return False
```

### 5. FastAPI 优化
```bash
# 启动命令优化
uvicorn server:app --host 0.0.0.0 --port 8000 --workers 4 --loop uvloop
```

## 预期性能提升

| 优化项 | 当前耗时 | 优化后耗时 | 提升比例 |
|--------|----------|------------|----------|
| 浏览器启动 | 2-3秒 | 0.1秒 (复用) | 95%↓ |
| 页面等待 | 10-20秒 | 2-5秒 | 75%↓ |
| 图片下载 | 30-60秒 | 15-30秒 | 50%↓ |
| **总计** | **42-83秒** | **17-35秒** | **58%↓** |

## 实施步骤

1. **第一阶段**：实现浏览器实例复用
2. **第二阶段**：优化等待逻辑和并发策略  
3. **第三阶段**：改进重试机制和HTTP客户端池
4. **第四阶段**：部署多进程FastAPI

## 风险控制

- **兼容性**：确保优化后的代码仍能处理所有漫画网站
- **稳定性**：添加适当的错误处理和回退机制
- **资源使用**：监控内存和CPU使用，避免过度并发

通过以上优化，预计可以实现 **50%+ 的性能提升**，满足您的目标要求。