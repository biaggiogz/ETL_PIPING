import { useEffect, useRef } from 'react';
import { Box } from '@chakra-ui/react';
import * as d3 from 'd3';

export const TemperatureChart = ({ data, width = 800, height = 300 }) => {
  const svgRef = useRef();

  useEffect(() => {
    if (!data || data.length === 0) return;

    const svg = d3.select(svgRef.current);
    svg.selectAll("*").remove();

    const margin = { top: 20, right: 30, bottom: 40, left: 50 };
    const innerWidth = width - margin.left - margin.right;
    const innerHeight = height - margin.top - margin.bottom;

    const xScale = d3.scaleTime()
      .domain(d3.extent(data, d => new Date(d.timestamp)))
      .range([0, innerWidth]);

    const yScale = d3.scaleLinear()
      .domain(d3.extent(data, d => d.temperature))
      .range([innerHeight, 0]);

    const line = d3.line()
      .x(d => xScale(new Date(d.timestamp)))
      .y(d => yScale(d.temperature))
      .curve(d3.curveMonotoneX);

    const g = svg.append('g')
      .attr('transform', `translate(${margin.left},${margin.top})`);

    g.append('g')
      .attr('transform', `translate(0,${innerHeight})`)
      .call(d3.axisBottom(xScale).tickFormat(d3.timeFormat('%H:%M:%S')));

    g.append('g')
      .call(d3.axisLeft(yScale));

    g.append('path')
      .datum(data)
      .attr('fill', 'none')
      .attr('stroke', '#3182ce')
      .attr('stroke-width', 2)
      .attr('d', line);

    g.selectAll('.dot')
      .data(data.slice(-10))
      .enter().append('circle')
      .attr('class', 'dot')
      .attr('cx', d => xScale(new Date(d.timestamp)))
      .attr('cy', d => yScale(d.temperature))
      .attr('r', 4)
      .attr('fill', '#e53e3e');

  }, [data, width, height]);

  return (
    <Box>
      <svg ref={svgRef} width={width} height={height}></svg>
    </Box>
  );
};