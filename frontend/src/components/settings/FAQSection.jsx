import React, { useState } from "react"
import { Card, CardHeader, CardTitle, CardContent } from "../ui/card"
import { Info, ChevronDown } from "lucide-react"

const FAQSection = ({ faqItems }) => {
  const [expandedFaq, setExpandedFaq] = useState(null)

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Info className="h-5 w-5" />
          常见问题 (FAQ)
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-2">
          {faqItems.map((item) => (
            <div key={item.id} className="border border-surface-high rounded-lg overflow-hidden">
              <button
                onClick={() => setExpandedFaq(expandedFaq === item.id ? null : item.id)}
                className="w-full flex items-center justify-between p-4 bg-surface-container/50 hover:bg-surface-high transition-colors"
                aria-label="展开"
              >
                <span className="text-text-primary font-medium">{item.question}</span>
                <ChevronDown className="h-4 w-4 text-text-secondary shrink-0" />
              </button>
              {expandedFaq === item.id && (
                <div className="p-4 bg-surface/50 text-text-secondary whitespace-pre-line">
                  {item.answer}
                </div>
              )}
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  )
}

export default FAQSection
