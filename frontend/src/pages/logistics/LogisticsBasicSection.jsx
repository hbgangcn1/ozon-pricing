import React from 'react'
import { Input } from '../../components/ui/input'
import { Label } from '../../components/ui/label'
import { RadioGroup } from '../../components/ui/radio-group'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../../components/ui/select'
import { Switch } from '../../components/ui/switch'
import {
  FBP_COMPANY_OPTIONS,
  FBP_SERVICE_LEVEL_OPTIONS,
  SCORING_GROUP_OPTIONS,
} from './logisticsConstants'
import { FormField, FormRow, RadioLabel, SectionTitle } from './LogisticsFormFields'

export default function LogisticsBasicSection({ form, onFormFieldChange, onFulfillmentChange }) {
  return (
    <div>
      <SectionTitle>基本信息</SectionTitle>
      <div className="space-y-4">
        <FormField label="名称">
          <Input
            value={form.name}
            onChange={(event) => onFormFieldChange('name', event.target.value)}
            placeholder="请输入名称"
          />
        </FormField>

        <FormRow>
          <FormField label="发货类型">
            <Select value={form.fulfillment_type} onValueChange={onFulfillmentChange}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="rfbs">rFBS</SelectItem>
                <SelectItem value="fbp">FBP</SelectItem>
              </SelectContent>
            </Select>
          </FormField>
          <FormField label="目的国">
            <Select value={form.destination} onValueChange={(value) => onFormFieldChange('destination', value)}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="RU">俄罗斯(RU)</SelectItem>
                {(form.fulfillment_type === 'rfbs' || (form.fulfillment_type === 'fbp' && ['economy', 'standard'].includes(form.fbp_service_level))) && (
                  <>
                    <SelectItem value="KZ">哈萨克斯坦(KZ)</SelectItem>
                    <SelectItem value="BY">白俄罗斯(BY)</SelectItem>
                  </>
                )}
                {form.fulfillment_type === 'rfbs' && (
                  <>
                    <SelectItem value="KGZ">吉尔吉斯斯坦(KGZ)</SelectItem>
                    <SelectItem value="UZ">乌兹别克斯坦(UZ)</SelectItem>
                    <SelectItem value="GE">格鲁吉亚(GE)</SelectItem>
                    <SelectItem value="AZ">阿塞拜疆(AZ)</SelectItem>
                  </>
                )}
              </SelectContent>
            </Select>
          </FormField>
        </FormRow>

        {form.fulfillment_type === 'fbp' && (
          <>
            <FormRow>
              <FormField label="FBP 服务等级" tooltip="FBP 仓库服务等级">
                <Select value={form.fbp_service_level} onValueChange={(value) => onFormFieldChange('fbp_service_level', value)}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {FBP_SERVICE_LEVEL_OPTIONS.map((option) => (
                      <SelectItem key={option.value} value={option.value}>{option.label}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </FormField>
              <FormField label="FBP 公司" tooltip="FBP 仓储服务公司代码">
                <Select value={form.fbp_company} onValueChange={(value) => onFormFieldChange('fbp_company', value)}>
                  <SelectTrigger><SelectValue placeholder="选择 FBP 公司" /></SelectTrigger>
                  <SelectContent>
                    {FBP_COMPANY_OPTIONS.map((option) => (
                      <SelectItem key={option} value={option}>{option}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </FormField>
            </FormRow>
            <FormRow>
              <FormField label="评分组 (Scoring Group)" tooltip="FBP 评分分组，影响定价分组逻辑">
                <Select value={form.scoring_group} onValueChange={(value) => onFormFieldChange('scoring_group', value)}>
                  <SelectTrigger><SelectValue placeholder="选择评分组" /></SelectTrigger>
                  <SelectContent>
                    {SCORING_GROUP_OPTIONS.map((option) => (
                      <SelectItem key={option} value={option}>{option}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </FormField>
              <FormField label="FBP Smart物流方式" tooltip="启用后该物流将属于Smart物流方式">
                <div className="flex items-center space-x-3">
                  <Switch
                    checked={form.is_smart === 1}
                    onCheckedChange={(value) => onFormFieldChange('is_smart', value ? 1 : 0)}
                  />
                  <Label className="text-sm text-text-secondary">{form.is_smart === 1 ? 'Smart' : '普通'}</Label>
                </div>
              </FormField>
            </FormRow>
          </>
        )}

        <FormRow>
          <FormField label="配送方式" tooltip="取货点或送货上门">
            <Select value={form.delivery_method} onValueChange={(value) => onFormFieldChange('delivery_method', value)}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="pickup">取货点</SelectItem>
                <SelectItem value="door">送货上门</SelectItem>
              </SelectContent>
            </Select>
          </FormField>
        </FormRow>

        <FormField label="物流类型">
          <RadioGroup
            value={form.type}
            onValueChange={(value) => onFormFieldChange('type', value)}
            className="flex flex-wrap gap-4"
          >
            <RadioLabel label="陆运" value="land" itemClassName="mt-0.5" />
            <RadioLabel label="空运" value="air" itemClassName="mt-0.5" />
          </RadioGroup>
        </FormField>

        <FormRow>
          <FormField label="最快时效(天)，未知就填0">
            <Input
              type="number"
              min="0"
              value={form.min_days}
              onChange={(event) => onFormFieldChange('min_days', event.target.value)}
              placeholder="0"
            />
          </FormField>
          <FormField label="最慢时效(天)，未知就填0">
            <Input
              type="number"
              min="0"
              value={form.max_days}
              onChange={(event) => onFormFieldChange('max_days', event.target.value)}
              placeholder="0"
            />
          </FormField>
        </FormRow>
      </div>
    </div>
  )
}
