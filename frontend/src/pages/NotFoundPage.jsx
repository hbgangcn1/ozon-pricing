import { Link } from 'react-router-dom'
import { FileQuestion } from 'lucide-react'
import { Button } from '../components/ui/button'

export default function NotFoundPage() {
  return (
    <div className="min-h-[80vh] flex flex-col items-center justify-center text-center px-4">
      <FileQuestion className="w-16 h-16 text-muted-foreground mb-4" />
      <h1 className="text-4xl font-bold mb-2">404</h1>
      <h2 className="text-xl font-semibold text-muted-foreground mb-6">页面不存在</h2>
      <p className="text-muted-foreground mb-8 max-w-md">
        您访问的页面已被移除、重命名，或者暂时不可用。
      </p>
      <Button asChild>
        <Link to="/">返回首页</Link>
      </Button>
    </div>
  )
}
