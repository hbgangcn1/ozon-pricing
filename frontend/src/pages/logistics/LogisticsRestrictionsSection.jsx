import React from 'react'
import { Checkbox } from '../../components/ui/checkbox'
import { Input } from '../../components/ui/input'
import { Label } from '../../components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../../components/ui/select'
import { FormField, FormRow, SectionTitle } from './LogisticsFormFields'

export default function LogisticsRestrictionsSection({ form, onFormFieldChange }) {
  return (
    <>
      <div>
        <SectionTitle>重量限制</SectionTitle>
        <FormRow>
          <FormField label="最小重量(g)" tooltip="允许运送的最小重量">
            <Input
              type="number"
              step="0.1"
              min="0"
              value={form.min_weight}
              onChange={(event) => onFormFieldChange('min_weight', event.target.value)}
              placeholder="0"
            />
          </FormField>
          <FormField label="最大重量(g)" tooltip="允许运送的最大重量，0表示无上限">
            <Input
              type="number"
              step="0.1"
              min="0"
              value={form.max_weight}
              onChange={(event) => onFormFieldChange('max_weight', event.target.value)}
              placeholder="无上限"
            />
          </FormField>
        </FormRow>
      </div>

      <div>
        <SectionTitle>体积重量计费方式</SectionTitle>
        <FormField label="体积重量计费方式" tooltip="当实际重量与体积重量不同时的计费规则">
          <Select value={form.volume_mode} onValueChange={(value) => onFormFieldChange('volume_mode', value)}>
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="none">不计算体积重量</SelectItem>
              <SelectItem value="max_actual_vs_volume">取实际重量与体积重量较大者</SelectItem>
              <SelectItem value="longest_side">最长边超过阈值时按体积重量计费</SelectItem>
              <SelectItem value="sum_of_sides">三边和超过阈值时按体积重量计费</SelectItem>
            </SelectContent>
          </Select>
        </FormField>
        {(form.volume_mode === 'longest_side' || form.volume_mode === 'sum_of_sides' || form.volume_mode === 'max_actual_vs_volume') && (
          <FormRow className="mt-3">
            {form.volume_mode === 'longest_side' && (
              <FormField label="最长边阈值(cm)" tooltip="当最长边超过此值时，按体积重量计费">
                <Input
                  type="number"
                  min="0"
                  value={form.longest_side_threshold}
                  onChange={(event) => onFormFieldChange('longest_side_threshold', event.target.value)}
                  placeholder="0"
                />
              </FormField>
            )}
            {form.volume_mode === 'sum_of_sides' && (
              <FormField label="三边和阈值(cm)" tooltip="当长+宽+高超过此值时，按体积重量计费">
                <Input
                  type="number"
                  min="0"
                  value={form.sum_of_sides_threshold}
                  onChange={(event) => onFormFieldChange('sum_of_sides_threshold', event.target.value)}
                  placeholder="0"
                />
              </FormField>
            )}
            <FormField label="体积重量系数" tooltip="体积重量 = 长×宽×高 / 系数 × 1000 (g)">
              <Input
                type="number"
                min="0"
                value={form.volume_coefficient}
                onChange={(event) => onFormFieldChange('volume_coefficient', event.target.value)}
                placeholder="6000"
              />
            </FormField>
          </FormRow>
        )}
      </div>

      <div>
        <SectionTitle>标准包装</SectionTitle>
        <FormRow className="mt-3">
          <FormField label="三边之和上限(cm)" tooltip="长+宽+高的总和上限">
            <Input
              type="number"
              min="0"
              value={form.max_sum_of_sides}
              onChange={(event) => onFormFieldChange('max_sum_of_sides', event.target.value)}
              placeholder="0"
            />
          </FormField>
        </FormRow>
        <FormRow className="mt-3">
          <FormField label="最长边上限(cm)" tooltip="最大单边长度上限">
            <Input
              type="number"
              min="0"
              value={form.max_longest_side}
              onChange={(event) => onFormFieldChange('max_longest_side', event.target.value)}
              placeholder="0"
            />
          </FormField>
          <FormField label="最长边下限(cm)" tooltip="最大单边长度下限，0表示无下限">
            <Input
              type="number"
              min="0"
              value={form.min_length}
              onChange={(event) => onFormFieldChange('min_length', event.target.value)}
              placeholder="0"
            />
          </FormField>
        </FormRow>
        <FormRow className="mt-3">
          <FormField label="第二边长上限(cm)" tooltip="第二长边的长度上限">
            <Input
              type="number"
              min="0"
              value={form.max_second_side}
              onChange={(event) => onFormFieldChange('max_second_side', event.target.value)}
              placeholder="0"
            />
          </FormField>
          <FormField label="第二边长下限(cm)" tooltip="第二长边的长度下限，0表示无下限">
            <Input
              type="number"
              min="0"
              value={form.min_second_side}
              onChange={(event) => onFormFieldChange('min_second_side', event.target.value)}
              placeholder="0"
            />
          </FormField>
        </FormRow>
        <FormRow className="mt-3">
          <FormField label="第三边长上限(cm)" tooltip="第三长边（最短边）的长度上限，0表示无上限">
            <Input
              type="number"
              min="0"
              value={form.max_third_side}
              onChange={(event) => onFormFieldChange('max_third_side', event.target.value)}
              placeholder="0"
            />
          </FormField>
        </FormRow>
      </div>

      <div>
        <SectionTitle>圆柱形包装</SectionTitle>
        <FormRow className="mt-3">
          <FormField label="2倍直径与长度之和限制(cm)" tooltip="(直径×2)+长度的上限">
            <Input
              type="number"
              min="0"
              value={form.max_cylinder_sum}
              onChange={(event) => onFormFieldChange('max_cylinder_sum', event.target.value)}
              placeholder="0"
            />
          </FormField>
          <FormField label="2倍直径与长度之和下限(cm)" tooltip="(直径×2)+长度的下限，0表示无下限">
            <Input
              type="number"
              min="0"
              value={form.min_cylinder_sum}
              onChange={(event) => onFormFieldChange('min_cylinder_sum', event.target.value)}
              placeholder="0"
            />
          </FormField>
        </FormRow>
        <FormRow className="mt-3">
          <FormField label="长度限制(cm)" tooltip="圆柱长度的上限">
            <Input
              type="number"
              min="0"
              value={form.max_cylinder_length}
              onChange={(event) => onFormFieldChange('max_cylinder_length', event.target.value)}
              placeholder="0"
            />
          </FormField>
          <FormField label="长度下限(cm)" tooltip="圆柱长度的下限，0表示无下限">
            <Input
              type="number"
              min="0"
              value={form.min_cylinder_length}
              onChange={(event) => onFormFieldChange('min_cylinder_length', event.target.value)}
              placeholder="0"
            />
          </FormField>
        </FormRow>
      </div>

      <div>
        <SectionTitle>价格限制</SectionTitle>
        <FormRow>
          <FormField label="价格上限（元）" tooltip="订单价格上限">
            <Input
              type="number"
              step="0.01"
              min="0"
              value={form.price_limit_cny}
              onChange={(event) => onFormFieldChange('price_limit_cny', event.target.value)}
              onBlur={(event) => {
                const value = event.target.value
                if (value !== '') onFormFieldChange('price_limit_cny', parseFloat(value).toFixed(2))
              }}
              placeholder="0.00"
            />
          </FormField>
          <FormField label="价格下限（元）" tooltip="订单价格下限">
            <Input
              type="number"
              step="0.01"
              min="0"
              value={form.price_min_cny}
              onChange={(event) => onFormFieldChange('price_min_cny', event.target.value)}
              onBlur={(event) => {
                const value = event.target.value
                if (value !== '') onFormFieldChange('price_min_cny', parseFloat(value).toFixed(2))
              }}
              placeholder="0.00"
            />
          </FormField>
        </FormRow>
      </div>

      <div>
        <SectionTitle>特殊物品限制</SectionTitle>
        <div className="flex flex-col sm:flex-row flex-wrap gap-4 sm:gap-6">
          <div className="flex items-center space-x-2">
            <Checkbox
              id="allow_battery"
              checked={form.allow_battery}
              onCheckedChange={(value) => onFormFieldChange('allow_battery', !!value)}
            />
            <Label htmlFor="allow_battery" className="text-sm cursor-pointer">
              允许电池
            </Label>
          </div>
          <div className="flex items-center space-x-2">
            <Checkbox
              id="allow_liquid"
              checked={form.allow_liquid}
              onCheckedChange={(value) => onFormFieldChange('allow_liquid', !!value)}
            />
            <Label htmlFor="allow_liquid" className="text-sm cursor-pointer">
              允许液体
            </Label>
          </div>
        </div>
      </div>
    </>
  )
}
